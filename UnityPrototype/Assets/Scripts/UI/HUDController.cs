using UnityEngine;
using UnityEngine.UI;

public class HUDController : MonoBehaviour
{
    [Header("Refs")]
    [SerializeField] private TimeSystem timeSystem;
    [SerializeField] private SurvivalComponent survival;
    [SerializeField] private InventoryComponent inventory;

    [Header("UI")]
    [SerializeField] private Text dayHourText;
    [SerializeField] private Text hungerText;
    [SerializeField] private Text healthText;
    [SerializeField] private Text carryWeightText;

    [SerializeField] private float refreshInterval = 0.2f;

    private float refreshTimer;

    private void Update()
    {
        refreshTimer -= Time.deltaTime;
        if (refreshTimer > 0f)
        {
            return;
        }

        refreshTimer = refreshInterval;

        if (timeSystem != null && dayHourText != null)
        {
            dayHourText.text = $"Day {timeSystem.Day}  {Mathf.FloorToInt(timeSystem.Hour):00}:00";
        }

        if (survival != null)
        {
            if (hungerText != null)
            {
                hungerText.text = $"Hunger: {survival.hunger:0}";
            }

            if (healthText != null)
            {
                healthText.text = $"Health: {survival.health:0}";
            }
        }

        if (inventory != null && carryWeightText != null)
        {
            carryWeightText.text = $"Carry: {inventory.CurrentWeight():0.0}/{inventory.maxCarryWeight:0.0}";
        }
    }
}
