// mission_checkpoints.h
// Fix for: "failed at the end and had to redo the whole drive", "restart loses my ammo".
//
// Approach:
//  * Authored checkpoints stay, but the system also inserts SOFT checkpoints when a stage
//    runs long (e.g. a 6-minute drive) at the next "safe" moment — not in combat, not
//    airborne, on the nav mesh.
//  * A checkpoint snapshots the loadout the player had when they reached it, and restores
//    it on retry (no ammo farming: the snapshot is of what they had, not a refill).
//  * After repeated failures of the same segment, offer to skip the travel portion
//    (the pattern players already know and like from earlier titles).
#pragma once
#include <string>
#include <unordered_map>
#include <vector>

#include "common.h"

namespace fp::missions {

struct PlayerSnapshot {
    Vec3 position;
    float health = 100.0f, armor = 0.0f;
    std::unordered_map<std::string, int> ammo;  // weapon id -> rounds
    std::string vehicleModel;                   // empty if on foot
};

struct SafetyQuery {  // filled by gameplay systems each frame
    bool inCombat = false;
    bool airborne = false;
    bool onNavMesh = true;
    bool inCutscene = false;
};

struct Checkpoint {
    std::string id;
    int stageIndex = 0;
    bool authored = true;
    PlayerSnapshot snapshot;
};

class CheckpointManager {
public:
    explicit CheckpointManager(std::string missionId) : missionId_(std::move(missionId)) {}

    void OnStageBegin(int stageIndex, const PlayerSnapshot& s);  // authored checkpoint
    void Tick(float dt, const SafetyQuery& safety, const PlayerSnapshot& current);
    // Returns the snapshot to restore on retry.
    const PlayerSnapshot& OnMissionFailed();
    bool ShouldOfferSkip() const;

    const std::vector<Checkpoint>& Checkpoints() const { return checkpoints_; }

private:
    std::string missionId_;
    std::vector<Checkpoint> checkpoints_;
    int stageIndex_ = 0;
    float timeSinceCheckpoint_ = 0.0f;
    std::unordered_map<std::string, int> failsPerCheckpoint_;
};

}  // namespace fp::missions
