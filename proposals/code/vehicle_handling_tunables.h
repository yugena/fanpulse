// vehicle_handling_tunables.h
// Fix for: "driving feels floaty / like ice", "bikes steer way too sensitive", "wish there was a slider".
//
// Players disagree with each other here (some love weighty handling), so the fix is not
// "change the physics". It's an ASSIST LAYER on top of the existing simulation:
//  * speed-sensitive steering (less lock at high speed — the main "twitchy bikes" cause),
//  * a counter-steer / yaw-damping assist that catches slides early,
//  * a wet-surface grip floor so rain doesn't turn every car into a drift car,
// all blended by one player-facing "Handling Assist" slider (0 = raw sim, 1 = full assist),
// with the DEFAULT set by a server tunable so we can move it after launch based on data.
#pragma once
#include "common.h"

namespace fp::vehicles {

enum class VehicleClass { Car, SportsCar, Motorbike, Truck };

struct DriverInput { float steer = 0; float throttle = 0; float brake = 0; };  // steer -1..1

struct VehicleState {
    VehicleClass cls = VehicleClass::Car;
    float speedMps = 0;
    float yawRate = 0;         // rad/s, measured
    float targetYawRate = 0;   // rad/s, what the steering geometry asks for
    float surfaceWetness = 0;  // 0..1
};

struct AssistOutput {
    float steer = 0;            // modified steering input
    float yawCorrectionTorque = 0;
    float gripMultiplier = 1;   // applied to tyre lateral grip
};

float PlayerAssistLevel();  // settings value, or tunable default if the player never touched it
AssistOutput ApplyHandlingAssist(const DriverInput& in, const VehicleState& s, float assistLevel);

}  // namespace fp::vehicles
