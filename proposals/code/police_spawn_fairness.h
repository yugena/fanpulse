// police_spawn_fairness.h
// Fix for: "cops spawn right behind / in front of me", "can't lose my stars".
//
// Two root causes usually sit behind this complaint:
//  1. Spawn selection only checks distance, not what the player can SEE or where
//     they're GOING, so units pop in inside the player's view or straight ahead.
//  2. Pursuers keep perfect knowledge of the player's position, so breaking line of
//     sight doesn't feel like it matters.
// The fix: score spawn candidates for fairness, and give the AI a last-known-position
// search model so hiding actually works.
#pragma once
#include <optional>
#include <vector>

#include "common.h"

namespace fp::police {

struct PlayerView {
    Vec3 position;
    Vec3 velocity;       // m/s, world space
    Vec3 cameraForward;  // normalized
    float cameraFovDeg = 60.0f;
};

struct SpawnCandidate {
    Vec3 position;
    Vec3 roadDirection;     // normalized lane direction at the node
    bool occludedFromCamera;  // result of an async raycast / occlusion query, already resolved
};

// Returns -1 to reject, else a score (higher = better).
float ScoreSpawn(const SpawnCandidate& c, const PlayerView& v, int wantedLevel);

// Picks the best candidate, or nothing (caller retries next frame — never force a bad spawn).
std::optional<SpawnCandidate> SelectSpawn(const std::vector<SpawnCandidate>& candidates,
                                          const PlayerView& v, int wantedLevel);

// ---- Search model --------------------------------------------------------------------------
// After line of sight is broken, units hunt a growing cone around the last-known position
// instead of tracking the player's live position.
class PursuitKnowledge {
public:
    void OnSeen(const Vec3& pos, const Vec3& vel);
    void Tick(float dt, bool anyUnitHasLineOfSight, const Vec3& truePlayerPos);

    bool IsSearching() const { return searching_; }
    // Where AI should navigate to. Never the true player position while searching.
    Vec3 InvestigatePoint() const;
    float SearchRadius() const;
    // True when the player has stayed outside the search area long enough to lose the stars.
    bool ShouldClearWanted(int wantedLevel) const;

private:
    Vec3 lastKnownPos_, lastKnownVel_;
    float timeSinceSeen_ = 0.0f;
    float timeOutsideSearch_ = 0.0f;
    bool searching_ = false;
};

}  // namespace fp::police
