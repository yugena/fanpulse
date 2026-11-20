// tests.cpp — build & run:  g++ -std=c++17 -Wall -Wextra -O2 *.cpp -o tests && ./tests
#include <cassert>
#include <cstdio>

#include "mission_checkpoints.h"
#include "police_spawn_fairness.h"
#include "streaming_prefetch.h"
#include "vehicle_handling_tunables.h"
#include "weapon_wheel_favorites.h"

using namespace fp;

static void TestPolice() {
    police::PlayerView v{{0, 0, 0}, {20, 0, 0}, {1, 0, 0}, 60.0f};
    // Visible spawn straight ahead -> rejected.
    assert(police::ScoreSpawn({{150, 0, 0}, {-1, 0, 0}, false}, v, 2) < 0);
    // Too close (behind, occluded) -> rejected.
    assert(police::ScoreSpawn({{-30, 0, 0}, {1, 0, 0}, true}, v, 2) < 0);
    // Occluded, dead ahead but within 6 s at 20 m/s (=120 m) -> rejected as a "teleport roadblock".
    assert(police::ScoreSpawn({{100, 0, 0}, {-1, 0, 0}, true}, v, 2) < 0);
    // Flank at a fair distance, road leading toward the player -> accepted.
    const float flank = police::ScoreSpawn({{0, 160, 0}, {0, -1, 0}, true}, v, 2);
    const float behind = police::ScoreSpawn({{-160, 0, 0}, {1, 0, 0}, true}, v, 2);
    assert(flank > 0 && behind >= 0 && flank > behind);  // flank preferred over dead-behind

    police::PursuitKnowledge k;
    k.OnSeen({0, 0, 0}, {10, 0, 0});
    for (int i = 0; i < 400; ++i) k.Tick(0.1f, false, {0, 2000, 0});  // player hid far away for 40 s
    assert(k.IsSearching());
    assert(k.InvestigatePoint().x == 40.0f);  // extrapolated 4 s, then stopped guessing
    assert(k.ShouldClearWanted(2));
    std::puts("police ok");
}

static void TestCheckpoints() {
    missions::CheckpointManager m("heist_01");
    missions::PlayerSnapshot start; start.ammo["pistol"] = 48;
    m.OnStageBegin(0, start);
    missions::PlayerSnapshot mid = start; mid.ammo["pistol"] = 12; mid.position = {500, 0, 0};
    missions::SafetyQuery combat; combat.inCombat = true;
    for (int i = 0; i < 200; ++i) m.Tick(1.0f, combat, mid);  // long stage, but in combat
    assert(m.Checkpoints().size() == 1);                     // never checkpoint mid-fight
    m.Tick(1.0f, missions::SafetyQuery{}, mid);              // first safe moment
    assert(m.Checkpoints().size() == 2 && !m.Checkpoints().back().authored);
    const auto& restored = m.OnMissionFailed();
    assert(restored.ammo.at("pistol") == 12 && restored.position.x == 500);  // no ammo refill
    m.OnMissionFailed(); assert(!m.ShouldOfferSkip());
    m.OnMissionFailed(); assert(m.ShouldOfferSkip());
    std::puts("checkpoints ok");
}

static void TestStreaming() {
    streaming::CameraState cam{{0, 0, 0}, {60, 0, 0}, {1, 0, 0}};  // ~135 mph
    std::vector<streaming::AssetRequest> reqs = {
        {1, {50, 0, 0}, 5, 400, 100, false},     // close, ahead: needed now
        {2, {300, 0, 0}, 5, 400, 100, false},    // far ahead: needed in ~3 s
        {3, {-130, 0, 0}, 5, 400, 100, false},   // close-ish but behind: low urgency
    };
    assert(streaming::TimeToNeed(reqs[1], cam) < streaming::TimeToNeed(reqs[2], cam));
    auto plan = streaming::BuildPlan(reqs, cam, 500);
    assert(plan.decisions[0].first == 1 && plan.decisions[0].second == streaming::LoadDecision::LoadHigh);
    assert(plan.decisions[1].first == 2 && plan.decisions[1].second == streaming::LoadDecision::LoadLow);
    assert(plan.bytesScheduled <= 500);
    std::puts("streaming ok");
}

static void TestHandling() {
    vehicles::VehicleState bike{vehicles::VehicleClass::Motorbike, 50.0f, 0.0f, 0.0f, 0.0f};
    auto raw = vehicles::ApplyHandlingAssist({1.0f, 1, 0}, bike, 0.0f);
    auto full = vehicles::ApplyHandlingAssist({1.0f, 1, 0}, bike, 1.0f);
    assert(raw.steer == 1.0f && full.steer < 0.5f);  // high-speed lock reduced only with assist
    vehicles::VehicleState wetSlide{vehicles::VehicleClass::Car, 30.0f, 1.2f, 0.4f, 1.0f};
    auto a = vehicles::ApplyHandlingAssist({0.3f, 1, 0}, wetSlide, 1.0f);
    assert(a.yawCorrectionTorque < 0);                    // pushes against the over-rotation
    assert(a.gripMultiplier >= 0.85f);                    // wet grip floor holds
    assert(vehicles::PlayerAssistLevel() == 0.5f);        // server default used
    Tunables::Get().Set("veh.assist.default_level", 0.7f); // live re-tune, no patch
    assert(vehicles::PlayerAssistLevel() > 0.69f);
    std::puts("handling ok");
}

static void TestWeapons() {
    weapons::WeaponSelector w;
    w.Equip("pistol"); w.Equip("rifle");
    w.OnButton(true, 10.0f);
    assert(w.OnButton(false, 10.1f) == weapons::WheelAction::QuickSwap && w.Current() == "pistol");
    w.OnButton(true, 20.0f);
    assert(w.PollHold(20.3f) == weapons::WheelAction::OpenWheel);
    assert(w.OnButton(false, 20.5f) == weapons::WheelAction::None && w.Current() == "pistol");
    for (auto id : {"a", "b", "c", "d"}) assert(w.ToggleFavorite(id));
    assert(!w.ToggleFavorite("e"));
    assert(w.CycleFavorite(+1) == "a" && w.CycleFavorite(-1) == "d");
    assert(weapons::WeaponSelector::WheelTimeScale(false) == 1.0f);
    std::puts("weapons ok");
}

int main() {
    int64_t events = 0;
    Telemetry::Get().SetSink([&](const std::string&, const std::string&, const TelemetryValue&) { ++events; });
    TestPolice(); TestCheckpoints(); TestStreaming(); TestHandling(); TestWeapons();
    std::printf("all tests passed (%lld telemetry events)\n", static_cast<long long>(events));
}
