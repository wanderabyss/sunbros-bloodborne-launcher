// SPDX-License-Identifier: GPL-2.0-or-later
// bbport: in-game settings menu (Dear ImGui), drawn by the presenter into the swapchain image
// after the game frame, at display resolution. Insert (keyboard) or L3+R3 (gamepad) opens it;
// while it is open the game gets no pad/keyboard input. Settings live in bbport_settings.h.

#pragma once

#include <cstdint>
#include <string>
#include "common/types.h"
#include "video_core/renderer_vulkan/vk_common.h"

union SDL_Event;
struct SDL_Window;

namespace Vulkan {
class Instance;
}

namespace BbOverlay {

/// Present thread, once: the ImGui context and its Vulkan backend.
void Init(const Vulkan::Instance& instance, vk::Format format, u32 image_count);

/// Window thread, for every SDL event: true when the menu consumed it.
bool HandleEvent(const SDL_Event& event);
/// Turns SDL text input on while the menu edits a value (window thread, once per poll).
void UpdateTextInput(SDL_Window* window);

/// Whether anything is drawn this frame (menu open or FPS counter on).
bool Visible();

/// The "Preparing shaders" screen, which replaces everything else the overlay draws. Any thread.
void SetStartupScreen(bool shown);
/// Black with "Starting the game", through the warm-up and over the game's first frames (its grey
/// clear colour), until its first UI frame ends it.
void SetStartupCover(bool on);
/// The warm-up found real preparation to do: "Preparing shaders" shows instead of the cover.
void SetStartupFirstRun();
bool StartupFirstRun();
/// 0 to 1; below 0 (the start) the amount of work is not known yet.
void SetStartupProgress(float fraction);
/// The player asked to go on without the remaining shaders (the controller's Options or Menu,
/// Esc, or a click on Skip).
bool StartupSkipRequested();
/// Window thread, once per poll: holds the controllers open while that screen is shown and reads
/// the skip button. The game opens its own only once it runs (runtime_pad.c).
void UpdateStartupPads();

/// Present thread: draws into `view` (layout ColorAttachmentOptimal).
void Render(vk::CommandBuffer cmdbuf, vk::ImageView view, vk::Extent2D extent);
/// Present thread, on frames Render is skipped (nothing visible): scripted tests' map commands
/// and trace (BB_MAP_TEST_CONTROL), which Render otherwise polls. Nothing without the variable.
void PollTests();
/// Every presented image, generated frames included (FPS readout; BB_FPS_LOG=1 prints the rate
/// every 5 seconds).
void NotePresent();

/// The menu is open or a text entry is shown: the game's input is held neutral.
bool CapturesInput();
/// Hunter's Atlas: the pad buttons left for the game once the Map tile and the open map
/// take theirs.
uint32_t RoutePad(uint32_t buttons, uint8_t lx, uint8_t ly, uint8_t rx, uint8_t ry);
/// The mouse belongs to a menu (settings, map, the Map tile): no mouse camera.
bool ReleasesMouse();

/// Window thread: the game's text dialog (sceImeDialog). Shown as a box on screen until
/// `active` is false; typing goes to the window (sdl_window), the box only displays it.
void SetTextEntry(bool active, const std::string& prompt, const std::string& text);
void LoadTrophies(const std::int64_t* timestamps, unsigned count);
void TrophyUnlocked(int id);

} // namespace BbOverlay
