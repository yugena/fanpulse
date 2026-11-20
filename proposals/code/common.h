// common.h — minimal stand-ins for engine services so every proposal compiles and is
// unit-testable on its own. In a real engine these map to the existing math library,
// the server-driven tunables system, the telemetry pipeline and the feature-flag service.
//
// NOTE: This is NOT Rockstar/RAGE code. It's an engine-agnostic illustration of how I'd
// structure each fix. Names and interfaces are mine.
#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <functional>
#include <string>
#include <unordered_map>
#include <variant>

namespace fp {

// ---------------------------------------------------------------- math
struct Vec3 {
    float x = 0, y = 0, z = 0;
    Vec3 operator+(const Vec3& o) const { return {x + o.x, y + o.y, z + o.z}; }
    Vec3 operator-(const Vec3& o) const { return {x - o.x, y - o.y, z - o.z}; }
    Vec3 operator*(float s) const { return {x * s, y * s, z * s}; }
    float Dot(const Vec3& o) const { return x * o.x + y * o.y + z * o.z; }
    float Length() const { return std::sqrt(Dot(*this)); }
    Vec3 Normalized() const { float l = Length(); return l > 1e-6f ? *this * (1.0f / l) : Vec3{}; }
};
inline float Clamp01(float v) { return std::clamp(v, 0.0f, 1.0f); }
inline float Lerp(float a, float b, float t) { return a + (b - a) * t; }
inline float SmoothStep(float e0, float e1, float x) {
    float t = Clamp01((x - e0) / (e1 - e0));
    return t * t * (3 - 2 * t);
}

// ---------------------------------------------------------------- tunables
// Server-pushed values (cloud "tunables"). The key point for live-ops: designers can
// re-balance these WITHOUT a code patch, so no platform certification round-trip.
class Tunables {
public:
    static Tunables& Get() { static Tunables t; return t; }
    float F(const std::string& key, float fallback) const {
        auto it = values_.find(key);
        return it == values_.end() ? fallback : it->second;
    }
    void Set(const std::string& key, float v) { values_[key] = v; }  // called by the tunables download
private:
    std::unordered_map<std::string, float> values_;
};
#define TUNABLE(key, fallback) ::fp::Tunables::Get().F(key, fallback)

// ---------------------------------------------------------------- feature flags
class Features {
public:
    static Features& Get() { static Features f; return f; }
    bool On(const std::string& name, bool fallback = false) const {
        auto it = flags_.find(name);
        return it == flags_.end() ? fallback : it->second;
    }
    void Set(const std::string& name, bool on) { flags_[name] = on; }
private:
    std::unordered_map<std::string, bool> flags_;
};

// ---------------------------------------------------------------- telemetry
// Every fix ships with the metric that proves (or disproves) it worked.
using TelemetryValue = std::variant<int64_t, double, std::string>;
class Telemetry {
public:
    using Sink = std::function<void(const std::string&, const std::string&, const TelemetryValue&)>;
    static Telemetry& Get() { static Telemetry t; return t; }
    void SetSink(Sink s) { sink_ = std::move(s); }
    void Emit(const std::string& event, const std::string& field, TelemetryValue v) {
        if (sink_) sink_(event, field, v);
    }
private:
    Sink sink_;
};

}  // namespace fp
