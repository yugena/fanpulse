// streaming_prefetch.h
// Fix for: "textures pop in when driving/flying fast", "frame drops at speed".
//
// Root cause pattern: streaming requests are prioritised by DISTANCE to the player. At
// high speed, the asset that matters is the one you'll SEE soonest — which can be far away
// but dead ahead. Distance priority also over-spends on assets behind you.
// Fix: prioritise by estimated time-until-visible along the predicted path, keep a hard
// per-frame I/O budget, and degrade to a lower LOD instead of stalling the frame.
#pragma once
#include <cstdint>
#include <vector>

#include "common.h"

namespace fp::streaming {

struct AssetRequest {
    uint32_t assetId = 0;
    Vec3 boundsCenter;
    float boundsRadius = 1.0f;
    uint32_t bytesHighLod = 0;
    uint32_t bytesLowLod = 0;
    bool resident = false;
};

struct CameraState {
    Vec3 position;
    Vec3 velocity;   // m/s
    Vec3 forward;    // normalized
};

enum class LoadDecision : uint8_t { Skip, LoadLow, LoadHigh };

struct Plan {
    std::vector<std::pair<uint32_t, LoadDecision>> decisions;  // in priority order
    uint32_t bytesScheduled = 0;
};

// Estimated seconds until the asset is on-screen and near enough to need high detail.
float TimeToNeed(const AssetRequest& a, const CameraState& cam);

// Schedules work within this frame's I/O budget.
Plan BuildPlan(std::vector<AssetRequest> requests, const CameraState& cam, uint32_t frameBudgetBytes);

}  // namespace fp::streaming
