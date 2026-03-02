# Unity Prototype Setup (Mac)

This folder contains a ready-to-import script pack for a first-person Oregon-Trail-style prototype.

## 1. Create/open your Unity project
- Open Unity Hub.
- Create a new 3D project (or open your existing one).
- Keep it on your Mac where you want it long-term.

## 2. Copy the scripts into Unity
- In Finder, open your Unity project folder.
- Copy `UnityPrototype/Assets/Scripts` from this workspace into your Unity project `Assets/` directory.
- Back in Unity Editor, wait for recompile.

## 3. Scene object wiring
Create these scene objects and attach scripts:

- `Systems` object:
  - `GameManager`
  - `TimeSystem`
  - `PartyManager`
  - `SaveSystem`
  - `EventEngine`

- `Player` object:
  - your FPS movement script
  - your mouse look script
  - `InventoryComponent`
  - `SurvivalComponent`
  - `InputRouter`
  - `PlayerStateLock`

- `Canvas` object:
  - `PanelController`
  - panels with exact IDs: `Shop`, `Camp`, `Event`, `Pause`
  - `HUDController`
  - `ShopUI`, `CampUI`, `EventUI`, `PauseUI`

## 4. Interactions
Add colliders to world objects and attach:
- `SettlementInteractable` for trade points
- `CampInteractable` for campfires
- `EventInteractable` for random events

## 5. Data assets
Create `ItemDefinition` assets for at least:
- Food
- Medicine
- Ammo (optional)

Create a few `EventDefinition` assets and assign them to `EventInteractable`.

## 6. Play test checklist
- Press `E` on settlement: shop opens
- Press `E` on camp: camp panel opens
- Press `E` on event: choice panel opens and applies effects
- Press `Esc`: pause panel toggles
- Camp/Pause save buttons produce a save file

## Notes
- UI scripts currently use `UnityEngine.UI` (`Text`, `Button`, `Dropdown`, `InputField`).
- `SaveSystem` currently stores core state (time/survival/money/party). Inventory serialization can be added next.
