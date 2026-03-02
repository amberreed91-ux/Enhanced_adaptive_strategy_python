using UnityEngine;
using UnityEngine.UI;

public class CampUI : MonoBehaviour
{
    [Header("Refs")]
    [SerializeField] private TimeSystem timeSystem;
    [SerializeField] private SurvivalComponent survival;
    [SerializeField] private SaveSystem saveSystem;
    [SerializeField] private PartyManager partyManager;
    [SerializeField] private ShopUI shopUI;
    [SerializeField] private PanelController panelController;

    [Header("UI")]
    [SerializeField] private Text resultText;
    [SerializeField] private Button restButton;
    [SerializeField] private Button medicineButton;
    [SerializeField] private Button saveButton;
    [SerializeField] private Button leaveButton;

    [Header("Camp tuning")]
    [SerializeField] private float restHours = 8f;
    [SerializeField] private float restHealthGain = 15f;
    [SerializeField] private float restHungerCost = 10f;
    [SerializeField] private float medicineHeal = 20f;

    private void OnEnable()
    {
        restButton.onClick.AddListener(Rest);
        medicineButton.onClick.AddListener(UseMedicine);
        saveButton.onClick.AddListener(Save);
        leaveButton.onClick.AddListener(Leave);
    }

    private void OnDisable()
    {
        restButton.onClick.RemoveListener(Rest);
        medicineButton.onClick.RemoveListener(UseMedicine);
        saveButton.onClick.RemoveListener(Save);
        leaveButton.onClick.RemoveListener(Leave);
    }

    private void Rest()
    {
        timeSystem.AdvanceHours(restHours);
        survival.hunger = Mathf.Max(0f, survival.hunger - restHungerCost);
        survival.health = Mathf.Min(100f, survival.health + restHealthGain);
        SetResult($"Rested for {restHours:0} hours.");
    }

    private void UseMedicine()
    {
        survival.health = Mathf.Min(100f, survival.health + medicineHeal);
        SetResult($"Used medicine (+{medicineHeal:0} health).");
    }

    private void Save()
    {
        saveSystem.Save(timeSystem, survival, partyManager, shopUI);
        SetResult("Game saved.");
    }

    private void Leave()
    {
        panelController.CloseAll();
    }

    private void SetResult(string message)
    {
        if (resultText != null)
        {
            resultText.text = message;
        }
    }
}
