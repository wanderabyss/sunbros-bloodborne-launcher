/* SPDX-License-Identifier: GPL-2.0-or-later
 * The game's 7.1 mix through Windows spatial sound. With Dolby Atmos for Headphones, Windows Sonic
 * or DTS on, the output still reports 2 channels, so the ordinary path folds the mix to stereo and
 * the spatial format only widens that. Here each channel goes to its static spatial audio object
 * (ISpatialAudioClient), so the format renders it from that speaker's position. With spatial sound
 * off nothing here runs. BB_AUDIO_SPATIAL=0 turns it off.
 *
 * Windows pulls a fixed quantum on its own event, on this file's thread; the game's audio thread
 * only fills the queue (spatial_ring.h). COM stays on that thread too: guest threads never see it.
 * When the output changes, the stream ends and the port returns to SDL, which follows the default
 * device. The stream is not started again until the next launch. */
#include "runtime_audio_spatial.h"

#ifdef _WIN32
#define COBJMACROS
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#include <objbase.h>
#include <mmdeviceapi.h>
#include <audioclient.h>
#include <spatialaudioclient.h>
#include <propidl.h>
#include <mmreg.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "spatial_ring.h"

/* Defined here rather than through initguid.h, which would define every GUID of those headers. */
static const GUID clsid_enumerator = {0xbcde0395, 0xe52f, 0x467c, {0x8e, 0x3d, 0xc4, 0x57, 0x92, 0x91, 0x69, 0x2e}};
static const GUID iid_enumerator = {0xa95664d2, 0x9614, 0x4f35, {0xa7, 0x46, 0xde, 0x8d, 0xb6, 0x36, 0x17, 0xe6}};
static const GUID iid_client = {0xbbf8e066, 0xaaaa, 0x49be, {0x9a, 0x4d, 0xfd, 0x2a, 0x85, 0x8e, 0xa2, 0x7f}};
static const GUID iid_stream = {0xbab5f473, 0xb423, 0x477b, {0x85, 0xf5, 0xb5, 0xa3, 0x32, 0xa0, 0x41, 0x53}};

/* In the queue's order, SDL's 7.1. */
static const AudioObjectType object_types[BB_SPATIAL_CHANNELS] = {
    AudioObjectType_FrontLeft, AudioObjectType_FrontRight, AudioObjectType_FrontCenter, AudioObjectType_LowFrequency,
    AudioObjectType_BackLeft,  AudioObjectType_BackRight,  AudioObjectType_SideLeft,    AudioObjectType_SideRight};

static BbSpatialRing ring;
static HANDLE thread_handle, ready_event;
static atomic_int stop_requested, ended;
static int started_ok;

/* Sets up the stream, as far as it goes. On failure says why, and returns NULL. */
static ISpatialAudioObjectRenderStream *start_stream(ISpatialAudioClient **client_out, HANDLE quantum_event) {
    IMMDeviceEnumerator *enumerator = NULL;
    IMMDevice *device = NULL;
    ISpatialAudioClient *client = NULL;
    ISpatialAudioObjectRenderStream *stream = NULL;
    const char *step = "the audio device list";
    HRESULT hr = CoCreateInstance(&clsid_enumerator, NULL, CLSCTX_ALL, &iid_enumerator, (void **)&enumerator);
    if (SUCCEEDED(hr)) {
        step = "the default output";
        hr = IMMDeviceEnumerator_GetDefaultAudioEndpoint(enumerator, eRender, eConsole, &device);
    }
    if (SUCCEEDED(hr)) {
        step = "the spatial audio client";
        hr = IMMDevice_Activate(device, &iid_client, CLSCTX_INPROC_SERVER, NULL, (void **)&client);
    }
    if (SUCCEEDED(hr)) {
        hr = ISpatialAudioClient_IsSpatialAudioStreamAvailable(client, &iid_stream, NULL);
        if (FAILED(hr)) {
            printf("Runtime: spatial sound: off (none on for this output, 0x%08lx); the mix goes through the ordinary path\n",
                   (unsigned long)hr);
            goto done;
        }
    }
    WAVEFORMATEX format = {WAVE_FORMAT_IEEE_FLOAT, 1, 48000, 48000 * 4, 4, 32, 0};
    if (SUCCEEDED(hr)) {
        step = "48 kHz float objects";
        hr = ISpatialAudioClient_IsAudioObjectFormatSupported(client, &format);
    }
    AudioObjectType mask = 0;
    for (int c = 0; c < BB_SPATIAL_CHANNELS; ++c) mask = (AudioObjectType)(mask | object_types[c]);
    if (SUCCEEDED(hr)) {
        step = "the stream";
        SpatialAudioObjectRenderStreamActivationParams params = {&format, mask, 0, 0, AudioCategory_GameEffects, quantum_event, NULL};
        PROPVARIANT activation;
        PropVariantInit(&activation);
        activation.vt = VT_BLOB;
        activation.blob.cbSize = sizeof(params);
        activation.blob.pBlobData = (BYTE *)&params;
        hr = ISpatialAudioClient_ActivateSpatialAudioStream(client, &activation, &iid_stream, (void **)&stream);
    }
    if (SUCCEEDED(hr)) {
        step = "starting the stream";
        hr = ISpatialAudioObjectRenderStream_Start(stream);
    }
    if (FAILED(hr)) {
        printf("Runtime: spatial sound: off (%s failed, 0x%08lx); the mix goes through the ordinary path\n", step, (unsigned long)hr);
        if (stream) ISpatialAudioObjectRenderStream_Release(stream);
        stream = NULL;
    }
done:
    if (device) IMMDevice_Release(device);
    if (enumerator) IMMDeviceEnumerator_Release(enumerator);
    if (stream) {
        *client_out = client;
    } else if (client) {
        ISpatialAudioClient_Release(client);
    }
    return stream;
}

static DWORD WINAPI spatial_thread(void *unused) {
    (void)unused;
    SetThreadPriority(GetCurrentThread(), THREAD_PRIORITY_HIGHEST);
    CoInitializeEx(NULL, COINIT_MULTITHREADED);
    HANDLE quantum_event = CreateEventW(NULL, FALSE, FALSE, NULL);
    ISpatialAudioClient *client = NULL;
    ISpatialAudioObjectRenderStream *stream = start_stream(&client, quantum_event);
    started_ok = stream != NULL;
    SetEvent(ready_event);
    if (stream) {
        ISpatialAudioObject *objects[BB_SPATIAL_CHANNELS] = {0};
        unsigned shown_underruns = 0, shown_dropped = 0;
        ULONGLONG shown_at = GetTickCount64();
        int late = 0;
        const char *why = NULL;
        HRESULT hr = S_OK;
        while (!atomic_load(&stop_requested)) {
            /* Windows stops signalling a stream it has invalidated. */
            if (WaitForSingleObject(quantum_event, 200) != WAIT_OBJECT_0) {
                if (++late >= 5) { why = "Windows stopped asking for audio"; break; }
                continue;
            }
            late = 0;
            UINT32 dynamic = 0, frames = 0;
            hr = ISpatialAudioObjectRenderStream_BeginUpdatingAudioObjects(stream, &dynamic, &frames);
            if (FAILED(hr)) { why = "updating"; break; }
            float *out[BB_SPATIAL_CHANNELS] = {0};
            for (int c = 0; c < BB_SPATIAL_CHANNELS; ++c) {
                if (!objects[c]) {
                    hr = ISpatialAudioObjectRenderStream_ActivateSpatialAudioObject(stream, object_types[c], &objects[c]);
                    if (FAILED(hr)) { objects[c] = NULL; why = "a channel's object"; break; }
                }
                BYTE *buffer = NULL;
                UINT32 bytes = 0;
                hr = ISpatialAudioObject_GetBuffer(objects[c], &buffer, &bytes);
                if (FAILED(hr)) { why = "a channel's buffer"; break; }
                if (bytes / sizeof(float) >= frames) out[c] = (float *)buffer;
            }
            if (!why) bb_spatial_ring_read(&ring, out, frames);
            ISpatialAudioObjectRenderStream_EndUpdatingAudioObjects(stream);
            if (why) break;
            const ULONGLONG now = GetTickCount64();
            if (now - shown_at >= 30000) {
                const unsigned underruns = atomic_load(&ring.underruns), dropped = atomic_load(&ring.dropped_frames);
                if (underruns != shown_underruns || dropped != shown_dropped) {
                    printf("Runtime: spatial sound: %u underruns, %u frames dropped in 30 s\n", underruns - shown_underruns, dropped - shown_dropped);
                    fflush(stdout);
                }
                shown_underruns = underruns;
                shown_dropped = dropped;
                shown_at = now;
            }
        }
        if (why) {
            printf("Runtime: spatial sound: ended (%s, 0x%08lx); back to the ordinary path\n", why, (unsigned long)hr);
            fflush(stdout);
        }
        atomic_store(&ended, 1);
        ISpatialAudioObjectRenderStream_Stop(stream);
        for (int c = 0; c < BB_SPATIAL_CHANNELS; ++c)
            if (objects[c]) ISpatialAudioObject_Release(objects[c]);
        ISpatialAudioObjectRenderStream_Release(stream);
        ISpatialAudioClient_Release(client);
    }
    CloseHandle(quantum_event);
    CoUninitialize();
    return 0;
}

int runtime_audio_spatial_open(void) {
    const char *setting = getenv("BB_AUDIO_SPATIAL");
    if ((setting && !strcmp(setting, "0")) || thread_handle) return 0;
    atomic_store(&ring.written, 0);
    atomic_store(&ring.taken, 0);
    ring.playing = 0;
    atomic_store(&stop_requested, 0);
    atomic_store(&ended, 0);
    ready_event = CreateEventW(NULL, TRUE, FALSE, NULL);
    thread_handle = CreateThread(NULL, 0, spatial_thread, NULL, 0, NULL);
    if (!thread_handle) {
        CloseHandle(ready_event);
        return 0;
    }
    WaitForSingleObject(ready_event, 5000);
    CloseHandle(ready_event);
    if (!started_ok) {
        runtime_audio_spatial_close();
        return 0;
    }
    puts("Runtime: spatial sound: on, the game's 8 channels go to their own speaker positions");
    return 1;
}

int runtime_audio_spatial_write(const float *frames, uint32_t count) {
    if (atomic_load(&ended)) return 0;
    bb_spatial_ring_write(&ring, frames, count);
    return 1;
}

void runtime_audio_spatial_close(void) {
    if (!thread_handle) return;
    atomic_store(&stop_requested, 1);
    WaitForSingleObject(thread_handle, 2000);
    CloseHandle(thread_handle);
    thread_handle = NULL;
}
#else
int runtime_audio_spatial_open(void) { return 0; }
int runtime_audio_spatial_write(const float *frames, uint32_t count) { (void)frames; (void)count; return 0; }
void runtime_audio_spatial_close(void) {}
#endif
