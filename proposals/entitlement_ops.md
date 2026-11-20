# Missing / already-redeemed download codes: an ops fix, not a game patch

**Type:** ops · **Ships as:** support process + partner escalation (no game code)

Not every top complaint is fixed in the game files. Physical "code in a box" editions arriving with no code, or a code that was already redeemed, are a **supply-chain and entitlement** problem. The senior-engineer answer is to route it correctly and quickly, not to write C++.

## What I'd do in week one
1. **Triage pipeline:** tag these reports in support tooling, automatically, from FanPulse's `store_codes` theme. Collect retailer, platform, and the batch/lot number from the box.
2. **Find the batch:** if failures cluster by lot number, it's a printing or pairing defect. Escalate to the manufacturing partner and the platform holder (code pools are issued per platform).
3. **Support macro:** a single verified path to a replacement entitlement (proof of purchase + lot photo), so tickets aren't closed without a resolution.
4. **Retail comms:** brief retailers that swaps for this issue are approved, so customers don't get turned away at the counter.
5. **Metric:** time to resolution for this ticket category, and the reopen rate.

## Why it belongs in the report
A player's view of "the game" includes buying and installing it. Ranking this next to gameplay issues, and labelling it `ops`, sends it to the right team instead of the patch backlog.
