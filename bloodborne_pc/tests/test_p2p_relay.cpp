// SPDX-License-Identifier: GPL-2.0-or-later
// BBSC relay fallback (gpu/bbnet/vendor/shadps4/core/net/p2p_relay.cpp): registration, routing
// and the frames the relay brings, without a network.
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#include "core/net/p2p_relay.h"

using Core::Net::P2P::Endpoint;
using Core::Net::P2P::Relay;

namespace {

u32 Addr(u8 a, u8 b, u8 c, u8 d) {
    return htonl((static_cast<u32>(a) << 24) | (static_cast<u32>(b) << 16) |
                 (static_cast<u32>(c) << 8) | d);
}

Endpoint V4(u32 addr_nbo, u16 port) {
    Endpoint e;
    auto* in = reinterpret_cast<sockaddr_in*>(&e.addr);
    in->sin_family = AF_INET;
    in->sin_addr.s_addr = addr_nbo;
    in->sin_port = htons(port);
    return e;
}

std::vector<u8> Bytes(const char* text) {
    return std::vector<u8>(text, text + std::strlen(text));
}

std::vector<u8> FromRelay(u8 kind, const std::string& id, u32 ep_addr, u16 ep_port,
                          const std::vector<u8>& frame) {
    std::vector<u8> p = {'B', 'B', 'R', '1', kind};
    std::string padded = id;
    padded.resize(16, '\0');
    p.insert(p.end(), padded.begin(), padded.end());
    if (kind == 0x04) {
        const u16 port_nbo = htons(ep_port);
        p.insert(p.end(), reinterpret_cast<const u8*>(&ep_addr), reinterpret_cast<const u8*>(&ep_addr) + 4);
        p.insert(p.end(), reinterpret_cast<const u8*>(&port_nbo), reinterpret_cast<const u8*>(&port_nbo) + 2);
        p.insert(p.end(), frame.begin(), frame.end());
    }
    return p;
}

} // namespace

int main() {
    Relay& relay = Relay::Instance();
    const u32 server = Addr(203, 0, 113, 7);
    const Endpoint peer = V4(Addr(198, 51, 100, 20), 3658);
    const Endpoint stranger = V4(Addr(198, 51, 100, 99), 4000);
    const std::vector<u8> datagram = Bytes("frame-1");
    std::vector<std::vector<u8>> relayed;

    // No server: everything direct, no registration.
    assert(relay.Route(datagram, peer, &relayed) == Relay::Path::Direct && relayed.empty());
    assert(!relay.NextKeepAlive());

    relay.SetServer(server);
    relay.SetLocalId("Hunter1");
    relay.SetSelfEndpoint(Addr(192, 0, 2, 1), htons(3658));
    relay.RememberPeer("Hunter2", Addr(198, 51, 100, 20), htons(3658));
    assert(relay.IsServer(V4(server, 3478)) && !relay.IsServer(V4(server, 31313)));

    // Registration "BBR1" 0x01 id[16], due at once.
    const auto now = Relay::Clock::now();
    const auto registration = relay.KeepAlive(now);
    assert(registration.size() == 1 && registration[0].size() == 21 && registration[0][4] == 0x01);
    assert(std::memcmp(registration[0].data() + 5, "Hunter1", 7) == 0 && registration[0][12] == 0);
    assert(relay.KeepAlive(now).empty()); // not again within 2 s

    // Before the relay answers: a known peer stays direct (no forced relay through a dead server).
    assert(relay.Route(datagram, peer, &relayed) == Relay::Path::Direct && relayed.empty());

    // The relay answers the registration: known peers go through it, with direct copies.
    std::vector<u8> frame;
    Endpoint from;
    assert(!relay.Receive(std::vector<u8>{'B', 'B', 'R', '1', 0x02}, &frame, &from));
    assert(relay.Route(datagram, peer, &relayed) == Relay::Path::Both);
    assert(!relayed.empty());
    const auto& out = relayed.back();
    assert(out[4] == 0x03 && std::memcmp(out.data() + 5, "Hunter2", 7) == 0 &&
           std::memcmp(out.data() + 21, "Hunter1", 7) == 0);
    assert(out.size() == 5 + 16 + 16 + 6 + datagram.size() &&
           std::memcmp(out.data() + 43, datagram.data(), datagram.size()) == 0);
    // An endpoint no peer has: direct.
    relayed.clear();
    assert(relay.Route(datagram, stranger, &relayed) == Relay::Path::Direct && relayed.empty());

    // The peer answers directly and never used the relay: direct from then on.
    relay.NoteDirect(peer);
    relayed.clear();
    assert(relay.Route(datagram, peer, &relayed) == Relay::Path::Direct && relayed.empty());

    // A frame through the relay from the peer arrives from the endpoint signaling knows.
    const std::vector<u8> payload = Bytes("hello");
    assert(relay.Receive(FromRelay(0x04, "Hunter2", Addr(100, 64, 0, 9), 50000, payload), &frame, &from));
    assert(frame == payload);
    assert(from == peer);
    // It uses the relay now: answers go through the relay only (it reached us directly before).
    relayed.clear();
    assert(relay.Route(datagram, peer, &relayed) == Relay::Path::Relay && relayed.size() == 1);

    // A peer signaling never looked up: filed under the endpoint it gave, answered by the relay.
    assert(relay.Receive(FromRelay(0x04, "Hunter3", Addr(100, 64, 0, 10), 50001, payload), &frame, &from));
    assert(from == V4(Addr(100, 64, 0, 10), 50001));
    relayed.clear();
    assert(relay.Route(datagram, from, &relayed) != Relay::Path::Direct && relayed.size() == 1);

    // "Not on the relay": that peer goes direct for a while.
    assert(!relay.Receive(FromRelay(0x05, "Hunter3", 0, 0, {}), &frame, &from));
    relayed.clear();
    assert(relay.Route(datagram, V4(Addr(100, 64, 0, 10), 50001), &relayed) == Relay::Path::Direct);

    // Off: no server, direct.
    relay.SetServer(0);
    relayed.clear();
    assert(relay.Route(datagram, peer, &relayed) == Relay::Path::Direct && relayed.empty());
    assert(!relay.NextKeepAlive());

    std::puts("p2p relay: ok");
    return 0;
}
