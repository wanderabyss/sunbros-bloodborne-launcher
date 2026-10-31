// SPDX-FileCopyrightText: Copyright 2026 shadPS4 Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

// bbport: BBSC's relay fallback for P2P (BBSC 0.0.2, CLS_AMG; github.com/CLSAMG22/BBSC
// bbport/bbport-1.7.2-bbsc.patch, network/p2p_sockets.cpp), on this transport.
//
// Direct P2P needs one side reachable: CGNAT, strict routers and several windows on one PC
// (no hairpin) leave both sides unreachable and the connection goes DEAD after 30 s. BBSC's game
// server runs a UDP relay on the shadNet server's address (port 3478) that forwards frames by
// online id:
//   "BBR1" 0x01 id[16]                        register, every 5 s (keeps our NAT mapping open)
//   "BBR1" 0x02                               registered
//   "BBR1" 0x03 dst[16] src[16] ep[6] frame   frame for dst
//   "BBR1" 0x04 src[16] ep[6] frame           frame from src
//   "BBR1" 0x05 dst[16]                       dst is not on the relay (direct only for 10 s)
// ep = the sender's public address and port as shadNet sees them (its STUN echo), so the receiver
// files the frame under the endpoint its signaling code uses for that peer. A frame is one whole
// UDP datagram of this transport, as it would have been sent directly.
//
// As in BBSC 0.0.2, every peer whose online id is known goes through the relay from its first
// frame, with direct copies until it answers either way; a peer that answers directly and never
// used the relay goes back to direct. Unlike BBSC, nothing goes through the relay before it has
// answered our registration (a server without the relay keeps every peer direct).
// SHADPS4_P2P_RELAY=0 (or off) turns it off; =auto (or direct) sends directly first and through
// the relay only after 2 s without a direct answer; =a.b.c.d:port uses another relay.
// SHADPS4_P2P_RELAY_PORT changes the port.

#pragma once

#include <chrono>
#include <mutex>
#include <optional>
#include <span>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

#include "core/net/p2p_transport.h"

namespace Core::Net::P2P {

class Relay {
public:
    using Clock = std::chrono::steady_clock;
    // Direct = send directly only; Relay = through the relay only; Both = relay + a direct copy.
    enum class Path { Direct, Relay, Both };

    static Relay& Instance();

    // From the NP side. Addresses and ports in network byte order, as signaling keeps them.
    void SetServer(u32 addr_nbo); // the shadNet server's address; 0 = no relay
    void SetSelfEndpoint(u32 addr_nbo, u16 port_nbo); // our public endpoint (STUN echo)
    void SetLocalId(std::string_view online_id);
    void RememberPeer(std::string_view online_id, u32 addr_nbo, u16 port_nbo);

    // From the IPv4 transport (its own mutex held; this class only takes its own).
    // A datagram for `to`: the packets for the relay server are added to `relayed`.
    Path Route(std::span<const u8> datagram, const Endpoint& to,
               std::vector<std::vector<u8>>* relayed);
    bool IsServer(const Endpoint& from) const;
    std::optional<Endpoint> Server() const;
    // A packet from the relay server: true with the frame and the peer's endpoint when it
    // carries a frame for this transport.
    bool Receive(std::span<const u8> packet, std::vector<u8>* frame, Endpoint* from);
    void NoteDirect(const Endpoint& from);
    // Registrations due now (to the server), and when the next one is due.
    std::vector<std::vector<u8>> KeepAlive(Clock::time_point now);
    std::optional<Clock::time_point> NextKeepAlive() const;

private:
    struct Peer {
        std::string id;
        u32 addr = 0; // the endpoint signaling uses: relayed frames arrive "from" it
        u16 port = 0;
        bool relayed = false;
        bool direct_rx = false;
        bool tx_started = false;
        bool relay_seen = false; // it sent to us through the relay (it has the relay too)
        Clock::time_point first_tx{};
        Clock::time_point relayed_since{};
        Clock::time_point missing_until{}; // the relay said it is not registered
        bool missing_logged = false;
        std::vector<std::vector<u8>> early; // sent directly before the switch (sent again then)
    };

    Relay() = default;
    static std::string PadId(std::string_view online_id);
    static u64 EndpointKey(u32 addr_nbo, u16 port_nbo);
    bool ActiveLocked() const;
    void AddAliasLocked(const std::string& id, u32 addr_nbo, u16 port_nbo, const char* from);
    Peer* FindPeerLocked(u32 addr_nbo, u16 port_nbo);
    std::vector<u8> RelayedLocked(const Peer& peer, std::span<const u8> datagram);

    mutable std::mutex mutex_;
    u32 server_addr_ = 0;
    u16 server_port_ = 0;
    bool force_ = true;
    bool acked_ = false;
    u32 self_addr_ = 0;
    u16 self_port_ = 0;
    Clock::time_point last_register_{};
    std::vector<std::string> local_ids_;
    std::unordered_map<std::string, Peer> peers_; // by padded online id
    std::unordered_map<u64, std::string> alias_;  // every known endpoint -> online id
    u32 next_pseudo_ = 1;
    u64 sent_ = 0;
    u64 received_ = 0;
    Clock::time_point last_status_{};
    u64 status_sent_ = 0;
    u64 status_received_ = 0;
};

} // namespace Core::Net::P2P
