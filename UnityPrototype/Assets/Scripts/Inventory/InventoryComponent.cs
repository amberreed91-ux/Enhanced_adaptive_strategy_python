using System.Collections.Generic;
using UnityEngine;

public class InventoryComponent : MonoBehaviour
{
    public List<InventorySlot> slots = new List<InventorySlot>();
    public float maxCarryWeight = 60f;

    public float CurrentWeight()
    {
        float total = 0f;

        for (int i = 0; i < slots.Count; i++)
        {
            InventorySlot slot = slots[i];
            if (slot.item != null)
            {
                total += slot.item.weight * slot.quantity;
            }
        }

        return total;
    }

    public int GetQuantity(ItemDefinition item)
    {
        if (item == null)
        {
            return 0;
        }

        int total = 0;
        for (int i = 0; i < slots.Count; i++)
        {
            if (slots[i].item == item)
            {
                total += slots[i].quantity;
            }
        }

        return total;
    }

    public bool TryAdd(ItemDefinition item, int qty)
    {
        if (item == null || qty <= 0)
        {
            return false;
        }

        float addedWeight = item.weight * qty;
        if (CurrentWeight() + addedWeight > maxCarryWeight)
        {
            return false;
        }

        int remaining = qty;

        for (int i = 0; i < slots.Count; i++)
        {
            InventorySlot slot = slots[i];
            if (slot.item != item || slot.quantity >= item.maxStack)
            {
                continue;
            }

            int capacity = item.maxStack - slot.quantity;
            int toAdd = Mathf.Min(capacity, remaining);
            slot.quantity += toAdd;
            remaining -= toAdd;

            if (remaining <= 0)
            {
                return true;
            }
        }

        while (remaining > 0)
        {
            int stackAmount = Mathf.Min(item.maxStack, remaining);
            slots.Add(new InventorySlot { item = item, quantity = stackAmount });
            remaining -= stackAmount;
        }

        return true;
    }

    public int Remove(ItemDefinition item, int qty)
    {
        if (item == null || qty <= 0)
        {
            return 0;
        }

        int toRemove = qty;

        for (int i = slots.Count - 1; i >= 0 && toRemove > 0; i--)
        {
            InventorySlot slot = slots[i];
            if (slot.item != item || slot.quantity <= 0)
            {
                continue;
            }

            int take = Mathf.Min(slot.quantity, toRemove);
            slot.quantity -= take;
            toRemove -= take;

            if (slot.quantity <= 0)
            {
                slots.RemoveAt(i);
            }
        }

        return qty - toRemove;
    }
}
