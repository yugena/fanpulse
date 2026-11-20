#include "police_spawn_fairness.h"

#include <cmath>

namespace fp::police {

namespace {
constexpr float kDegToRad = 3.14159265f / 180.0f;
}

float ScoreSpawn(const SpawnCandidate& c, const PlayerView& v, int wantedLevel) {
    const Vec3 toSpawn = c.position - v.position;
    const float dist = toSpawn.Length();
    const Vec3 dir = toSpawn.Normalized();

    // Hard rule 1: never inside a minimum bubble. Scales down a bit at high wanted
    // levels so 5 stars still feels intense.
    const float minDist = TUNABLE("police.spawn.min_dist", 90.0f) -
                          TUNABLE("police.spawn.min_dist_per_star", 8.0f) * float(wantedLevel);
    if (dist < minDist) return -1.0f;

    // Hard rule 2: never visibly pop in. Inside the (slightly widened) camera frustum and
    // not occluded -> reject.
    const float halfFov = 0.5f * v.cameraFovDeg * kDegToRad + TUNABLE("police.spawn.fov_pad_rad", 0.15f);
    const bool inFrustum = dir.Dot(v.cameraForward) > std::cos(halfFov);
    if (inFrustum && !c.occludedFromCamera) return -1.0f;

    // Hard rule 3: no "teleport roadblock" directly in the player's path at speed.
    const float speed = v.velocity.Length();
    if (speed > TUNABLE("police.spawn.ahead_check_speed", 8.0f)) {
        const float ahead = dir.Dot(v.velocity.Normalized());
        const float secondsToReach = dist / speed;
        if (ahead > 0.85f && secondsToReach < TUNABLE("police.spawn.min_reaction_s", 6.0f))
            return -1.0f;
    }

    // Soft preferences:
    float score = 0.0f;
    // Prefer a ring band around the ideal distance instead of "as close as legal".
    const float ideal = TUNABLE("police.spawn.ideal_dist", 160.0f);
    score += 1.0f - Clamp01(std::fabs(dist - ideal) / ideal);
    // Prefer spawns whose road leads TOWARD the player: units arrive driving in, which
    // reads as "they were dispatched", not "they materialised".
    score += 0.75f * Clamp01(c.roadDirection.Dot(dir * -1.0f));
    // Prefer flanks over dead-behind (behind-the-player spawns are the #1 complaint).
    const float behind = -dir.Dot(v.cameraForward);
    score -= 0.5f * SmoothStep(0.6f, 0.95f, behind);
    return score;
}

std::optional<SpawnCandidate> SelectSpawn(const std::vector<SpawnCandidate>& candidates,
                                          const PlayerView& v, int wantedLevel) {
    std::optional<SpawnCandidate> best;
    float bestScore = -1.0f;
    int rejected = 0;
    for (const auto& c : candidates) {
        const float s = ScoreSpawn(c, v, wantedLevel);
        if (s < 0.0f) { ++rejected; continue; }
        if (s > bestScore) { bestScore = s; best = c; }
    }
    // Metric: how often fairness rules starve dispatch. If this climbs, the tunables are
    // too strict for dense areas and the game will feel too easy.
    Telemetry::Get().Emit("police_spawn", "rejected", int64_t(rejected));
    if (!best) Telemetry::Get().Emit("police_spawn", "starved", int64_t(1));
    return best;
}

// ------------------------------------------------------------------ search model
void PursuitKnowledge::OnSeen(const Vec3& pos, const Vec3& vel) {
    lastKnownPos_ = pos;
    lastKnownVel_ = vel;
    timeSinceSeen_ = 0.0f;
    timeOutsideSearch_ = 0.0f;
    searching_ = false;
}

void PursuitKnowledge::Tick(float dt, bool anyUnitHasLineOfSight, const Vec3& truePlayerPos) {
    if (anyUnitHasLineOfSight) { OnSeen(truePlayerPos, lastKnownVel_); return; }
    searching_ = true;
    timeSinceSeen_ += dt;
    const bool inside = (truePlayerPos - InvestigatePoint()).Length() <= SearchRadius();
    timeOutsideSearch_ = inside ? 0.0f : timeOutsideSearch_ + dt;
}

Vec3 PursuitKnowledge::InvestigatePoint() const {
    // Extrapolate along the last seen heading for a short while, then stop guessing.
    const float t = std::min(timeSinceSeen_, TUNABLE("police.search.extrapolate_s", 4.0f));
    return lastKnownPos_ + lastKnownVel_ * t;
}

float PursuitKnowledge::SearchRadius() const {
    return TUNABLE("police.search.base_radius", 60.0f) +
           TUNABLE("police.search.growth_mps", 9.0f) * timeSinceSeen_;
}

bool PursuitKnowledge::ShouldClearWanted(int wantedLevel) const {
    const float need = TUNABLE("police.search.escape_s_base", 10.0f) +
                       TUNABLE("police.search.escape_s_per_star", 6.0f) * float(wantedLevel);
    return searching_ && timeOutsideSearch_ >= need;
}

}  // namespace fp::police
