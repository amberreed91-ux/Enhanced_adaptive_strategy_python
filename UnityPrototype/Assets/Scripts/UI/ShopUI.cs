using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

public class ShopUI : MonoBehaviour
{
    [System.Serializable]
    public class ShopEntry
    {
        public ItemDefinition item;
        public int price = 5;
    }

    [Header("Refs")]
    [SerializeField] private InventoryComponent playerInventory;
    [SerializeField] private PanelController panelController;

    [Header("UI")]
    [SerializeField] private Text moneyText;
    [SerializeField] private Dropdown itemDropdown;
    [SerializeField] private InputField quantityInput;
    [SerializeField] private Text resultText;
    [SerializeField] private Button buyButton;
    [SerializeField] private Button sellButton;
    [SerializeField] private Button closeButton;

    [Header("Data")]
    [SerializeField] private List<ShopEntry> stock = new List<ShopEntry>();
    [SerializeField] private int startingMoney = 100;

    public int PlayerMoney { get; private set; }

    private void Awake()
    {
        PlayerMoney = startingMoney;
    }

    private void OnEnable()
    {
        RebuildDropdown();
        RefreshMoney();
        SetResult(string.Empty);

        buyButton.onClick.AddListener(BuySelected);
        sellButton.onClick.AddListener(SellSelected);
        closeButton.onClick.AddListener(CloseShop);
    }

    private void OnDisable()
    {
        buyButton.onClick.RemoveListener(BuySelected);
        sellButton.onClick.RemoveListener(SellSelected);
        closeButton.onClick.RemoveListener(CloseShop);
    }

    public void SetMoney(int money)
    {
        PlayerMoney = Mathf.Max(0, money);
        RefreshMoney();
    }

    private void RebuildDropdown()
    {
        if (itemDropdown == null)
        {
            return;
        }

        itemDropdown.ClearOptions();
        List<string> options = new List<string>();

        for (int i = 0; i < stock.Count; i++)
        {
            ShopEntry entry = stock[i];
            if (entry.item == null)
            {
                continue;
            }

            options.Add($"{entry.item.displayName} (${entry.price})");
        }

        itemDropdown.AddOptions(options);
    }

    private int ParseQuantity()
    {
        if (quantityInput == null || !int.TryParse(quantityInput.text, out int qty))
        {
            return 1;
        }

        return Mathf.Max(1, qty);
    }

    private ShopEntry GetSelected()
    {
        if (itemDropdown == null || stock.Count == 0)
        {
            return null;
        }

        int idx = Mathf.Clamp(itemDropdown.value, 0, stock.Count - 1);
        return stock[idx];
    }

    private void BuySelected()
    {
        ShopEntry selected = GetSelected();
        if (selected == null || selected.item == null)
        {
            SetResult("No item selected.");
            return;
        }

        int qty = ParseQuantity();
        int totalPrice = selected.price * qty;

        if (PlayerMoney < totalPrice)
        {
            SetResult("Not enough money.");
            return;
        }

        if (!playerInventory.TryAdd(selected.item, qty))
        {
            SetResult("Too heavy to carry.");
            return;
        }

        PlayerMoney -= totalPrice;
        RefreshMoney();
        SetResult($"Bought {qty}x {selected.item.displayName}.");
    }

    private void SellSelected()
    {
        ShopEntry selected = GetSelected();
        if (selected == null || selected.item == null)
        {
            SetResult("No item selected.");
            return;
        }

        int qty = ParseQuantity();
        int removed = playerInventory.Remove(selected.item, qty);

        if (removed <= 0)
        {
            SetResult($"No {selected.item.displayName} to sell.");
            return;
        }

        int sellValue = Mathf.Max(1, selected.price / 2);
        PlayerMoney += removed * sellValue;
        RefreshMoney();
        SetResult($"Sold {removed}x {selected.item.displayName}.");
    }

    private void RefreshMoney()
    {
        if (moneyText != null)
        {
            moneyText.text = $"Money: ${PlayerMoney}";
        }
    }

    private void SetResult(string message)
    {
        if (resultText != null)
        {
            resultText.text = message;
        }
    }

    private void CloseShop()
    {
        panelController.CloseAll();
    }
}
