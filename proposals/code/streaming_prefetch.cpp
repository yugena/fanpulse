#include "streaming_prefetch.h"

#include <algorithm>
#include <limits>

namespace fp::streaming {

float TimeToNeed(const AssetRequest& a, const CameraState& cam) {
    const Vec3 to = a.boundsCenter - cam.position;
    const float dist = std::max(0.0f, to.Length() - a.boundsRadius);
    const float hiDetailDist = TUNABLE("stream.hi_detail_dist_m", 120.0f);
    if (dist <= hiDetailDist) return 0.0f;  // needed now

    const float speed = cam.velocity.Length();
    const Vec3 moveDir = speed > 0.5f ? cam.velocity * (1.0f / speed) : cam.forward;
    const float along = to.Normalized().Dot(moveDir);

    // Behind or beside us: only needed if we turn around — low urgency, distance based.
    if (along < 0.2f) return dist / TUNABLE("stream.turn_speed_mps", 15.0f);

    // Ahead: closing speed is the component of velocity toward the asset.
    const float closing = std::max(speed * along, 1.0f);
    return (dist - hiDetailDist) / closing;
}

Plan BuildPlan(std::vector<AssetRequest> requests, const CameraState& cam, uint32_t frameBudgetBytes) {
    struct Item { const AssetRequest* a; float t; };
    std::vector<Item> items;
    items.reserve(requests.size());
    for (const auto& r : requests)
        if (!r.resident) items.push_back({&r, TimeToNeed(r, cam)});
    std::sort(items.begin(), items.end(), [](const Item& x, const Item& y) { return x.t < y.t; });

    Plan plan;
    const float lookahead = TUNABLE("stream.lookahead_s", 4.0f);
    for (const auto& it : items) {
        if (it.t > lookahead) break;  // sorted: nothing later is urgent this frame
        const uint32_t left = frameBudgetBytes - plan.bytesScheduled;
        if (it.a->bytesHighLod <= left) {
            plan.decisions.push_back({it.a->assetId, LoadDecision::LoadHigh});
            plan.bytesScheduled += it.a->bytesHighLod;
        } else if (it.a->bytesLowLod <= left) {
            // Degrade instead of stalling: low LOD now, high LOD gets re-requested next frame.
            plan.decisions.push_back({it.a->assetId, LoadDecision::LoadLow});
            plan.bytesScheduled += it.a->bytesLowLod;
            Telemetry::Get().Emit("streaming", "degraded_to_low", int64_t(it.a->assetId));
        } else {
            plan.decisions.push_back({it.a->assetId, LoadDecision::Skip});
            if (it.t <= 0.0f)  // needed NOW and can't fit: this is a visible pop-in
                Telemetry::Get().Emit("streaming", "popin_risk", int64_t(it.a->assetId));
        }
    }
    return plan;
}

}  // namespace fp::streaming
