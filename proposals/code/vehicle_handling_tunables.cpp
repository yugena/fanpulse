#include "vehicle_handling_tunables.h"

#include <cmath>
#include <string>

namespace fp::vehicles {

namespace {
const char* ClassKey(VehicleClass c) {
    switch (c) {
        case VehicleClass::SportsCar: return "sports";
        case VehicleClass::Motorbike: return "bike";
        case VehicleClass::Truck:     return "truck";
        default:                      return "car";
    }
}
float T(VehicleClass c, const char* field, float fallback) {
    return TUNABLE(std::string("veh.assist.") + ClassKey(c) + "." + field, fallback);
}
}  // namespace

float PlayerAssistLevel() {
    // -1 means "player never changed it": use the live default we control server-side.
    const float user = TUNABLE("settings.handling_assist", -1.0f);
    return user >= 0.0f ? Clamp01(user) : Clamp01(TUNABLE("veh.assist.default_level", 0.5f));
}

AssistOutput ApplyHandlingAssist(const DriverInput& in, const VehicleState& s, float assist) {
    AssistOutput out;
    assist = Clamp01(assist);

    // 1) Speed-sensitive steering: at 0 m/s full lock, at high speed reduced lock.
    const float fadeStart = T(s.cls, "steer_fade_start_mps", 10.0f);
    const float fadeEnd   = T(s.cls, "steer_fade_end_mps", 45.0f);
    const float minLock   = T(s.cls, "steer_min_lock", s.cls == VehicleClass::Motorbike ? 0.35f : 0.5f);
    const float lockScale = Lerp(1.0f, minLock, SmoothStep(fadeStart, fadeEnd, s.speedMps));
    out.steer = in.steer * Lerp(1.0f, lockScale, assist);

    // 2) Yaw damping: if the car rotates faster than the steering asks for, push back.
    //    Proportional only — enough to catch a slide, not enough to feel like a rail.
    const float yawError = s.yawRate - s.targetYawRate;
    const float deadzone = T(s.cls, "yaw_deadzone", 0.08f);
    if (std::fabs(yawError) > deadzone) {
        const float gain = T(s.cls, "yaw_gain", 0.6f);
        out.yawCorrectionTorque = -yawError * gain * assist;
    }

    // 3) Wet grip floor: rain reduces grip, but never below a floor at full assist.
    const float wetLoss  = T(s.cls, "wet_grip_loss", 0.35f) * s.surfaceWetness;
    const float rawGrip  = 1.0f - wetLoss;
    const float floor    = T(s.cls, "wet_grip_floor", 0.85f);
    out.gripMultiplier = Lerp(rawGrip, std::max(rawGrip, floor), assist);
    return out;
}

}  // namespace fp::vehicles
