// weapon_wheel_favorites.h
// Fix for: "weapon wheel is slow in a firefight", "need quick swap to last weapon", "favourites".
//
//  * Tap the weapon-wheel button = swap to previous weapon (no wheel opens).
//    Hold = open wheel (existing behaviour). Tap/hold threshold is tunable.
//  * Up to 4 favourites per slot category, shown first on the wheel and cycled with d-pad.
//  * Optional (accessibility setting): stronger slow-mo while the wheel is open in single player.
#pragma once
#include <array>
#include <optional>
#include <string>
#include <vector>

#include "common.h"

namespace fp::weapons {

enum class WheelAction { None, QuickSwap, OpenWheel };

class WeaponSelector {
public:
    // Input edge events from the controller layer.
    WheelAction OnButton(bool pressed, float timeNow);
    WheelAction PollHold(float timeNow);  // call per frame while the button is down

    void Equip(std::string weaponId);  // by value: callers may pass previous_ itself
    const std::string& Current() const { return current_; }
    std::optional<std::string> Previous() const;

    bool ToggleFavorite(const std::string& weaponId);  // false if favourites are full
    const std::vector<std::string>& Favorites() const { return favorites_; }
    std::string CycleFavorite(int direction);           // d-pad left/right

    static float WheelTimeScale(bool singlePlayer);

private:
    std::string current_ = "unarmed";
    std::string previous_;
    std::vector<std::string> favorites_;
    int favIndex_ = -1;
    float pressTime_ = -1.0f;
    bool wheelOpened_ = false;
};

}  // namespace fp::weapons
