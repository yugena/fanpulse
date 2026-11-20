#include "weapon_wheel_favorites.h"

#include <algorithm>
#include <utility>

namespace fp::weapons {

WheelAction WeaponSelector::OnButton(bool pressed, float timeNow) {
    if (pressed) {
        pressTime_ = timeNow;
        wheelOpened_ = false;
        return WheelAction::None;
    }
    // Released: a short tap is a quick swap, unless the wheel already opened.
    const bool wasTap = !wheelOpened_ && pressTime_ >= 0.0f &&
                        (timeNow - pressTime_) < TUNABLE("weapons.tap_threshold_s", 0.18f);
    pressTime_ = -1.0f;
    if (wasTap && !previous_.empty()) {
        Equip(previous_);
        Telemetry::Get().Emit("weapon_wheel", "quick_swap", int64_t(1));
        return WheelAction::QuickSwap;
    }
    return WheelAction::None;
}

WheelAction WeaponSelector::PollHold(float timeNow) {
    if (pressTime_ < 0.0f || wheelOpened_) return WheelAction::None;
    if (timeNow - pressTime_ >= TUNABLE("weapons.tap_threshold_s", 0.18f)) {
        wheelOpened_ = true;
        return WheelAction::OpenWheel;
    }
    return WheelAction::None;
}

void WeaponSelector::Equip(std::string weaponId) {
    if (weaponId == current_) return;
    previous_ = current_;
    current_ = std::move(weaponId);
}

std::optional<std::string> WeaponSelector::Previous() const {
    return previous_.empty() ? std::nullopt : std::optional<std::string>(previous_);
}

bool WeaponSelector::ToggleFavorite(const std::string& weaponId) {
    auto it = std::find(favorites_.begin(), favorites_.end(), weaponId);
    if (it != favorites_.end()) { favorites_.erase(it); return true; }
    if (int(favorites_.size()) >= int(TUNABLE("weapons.max_favorites", 4.0f))) return false;
    favorites_.push_back(weaponId);
    return true;
}

std::string WeaponSelector::CycleFavorite(int direction) {
    if (favorites_.empty()) return current_;
    const int n = int(favorites_.size());
    favIndex_ = ((favIndex_ + (direction >= 0 ? 1 : -1)) % n + n) % n;
    Equip(favorites_[favIndex_]);
    return current_;
}

float WeaponSelector::WheelTimeScale(bool singlePlayer) {
    if (!singlePlayer) return 1.0f;  // never slow time in multiplayer
    return Features::Get().On("accessibility.strong_wheel_slowmo")
               ? TUNABLE("weapons.wheel_timescale_strong", 0.1f)
               : TUNABLE("weapons.wheel_timescale", 0.35f);
}

}  // namespace fp::weapons
