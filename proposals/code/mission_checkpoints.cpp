#include "mission_checkpoints.h"

namespace fp::missions {

void CheckpointManager::OnStageBegin(int stageIndex, const PlayerSnapshot& s) {
    stageIndex_ = stageIndex;
    timeSinceCheckpoint_ = 0.0f;
    checkpoints_.push_back({missionId_ + "/stage" + std::to_string(stageIndex), stageIndex, true, s});
}

void CheckpointManager::Tick(float dt, const SafetyQuery& safety, const PlayerSnapshot& current) {
    if (!Features::Get().On("missions.soft_checkpoints", true)) return;
    timeSinceCheckpoint_ += dt;

    const float interval = TUNABLE("missions.soft_checkpoint_interval_s", 150.0f);
    const bool safe = !safety.inCombat && !safety.airborne && safety.onNavMesh && !safety.inCutscene;
    if (timeSinceCheckpoint_ < interval || !safe) return;

    const int n = int(checkpoints_.size());
    checkpoints_.push_back({missionId_ + "/soft" + std::to_string(n), stageIndex_, false, current});
    timeSinceCheckpoint_ = 0.0f;
    Telemetry::Get().Emit("mission_checkpoint", "soft_inserted", missionId_);
}

const PlayerSnapshot& CheckpointManager::OnMissionFailed() {
    // Callers guarantee at least the stage-0 checkpoint exists (OnStageBegin(0) at mission start).
    const Checkpoint& last = checkpoints_.back();
    const int fails = ++failsPerCheckpoint_[last.id];
    Telemetry::Get().Emit("mission_fail", last.id, int64_t(fails));  // finds the "wall" segments
    return last.snapshot;
}

bool CheckpointManager::ShouldOfferSkip() const {
    if (checkpoints_.empty()) return false;
    auto it = failsPerCheckpoint_.find(checkpoints_.back().id);
    const int threshold = int(TUNABLE("missions.skip_offer_after_fails", 3.0f));
    return it != failsPerCheckpoint_.end() && it->second >= threshold;
}

}  // namespace fp::missions
