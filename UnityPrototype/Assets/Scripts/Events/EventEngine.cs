using UnityEngine;

public class EventEngine : MonoBehaviour
{
    [Header("Optional item refs for event deltas")]
    [SerializeField] private ItemDefinition foodItem;
    [SerializeField] private ItemDefinition medicineItem;

    public void ApplyChoice(EventChoice choice, InventoryComponent inventory, SurvivalComponent survival)
    {
        if (choice == null || inventory == null || survival == null)
        {
            return;
        }

        survival.health = Mathf.Clamp(survival.health + choice.hpDelta, 0f, 100f);

        ApplyInventoryDelta(inventory, foodItem, choice.foodDelta);
        ApplyInventoryDelta(inventory, medicineItem, choice.medicineDelta);

        Debug.Log($"Applied choice: {choice.text}");
    }

    private void ApplyInventoryDelta(InventoryComponent inventory, ItemDefinition item, int delta)
    {
        if (item == null || delta == 0)
        {
            return;
        }

        if (delta > 0)
        {
            inventory.TryAdd(item, delta);
            return;
        }

        inventory.Remove(item, Mathf.Abs(delta));
    }
}
