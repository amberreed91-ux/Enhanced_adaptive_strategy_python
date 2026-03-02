using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

public class EventUI : MonoBehaviour
{
    [Header("Refs")]
    [SerializeField] private EventEngine eventEngine;
    [SerializeField] private InventoryComponent inventory;
    [SerializeField] private SurvivalComponent survival;
    [SerializeField] private PanelController panelController;

    [Header("UI")]
    [SerializeField] private Text titleText;
    [SerializeField] private Text bodyText;
    [SerializeField] private List<Button> choiceButtons = new List<Button>();
    [SerializeField] private List<Text> choiceButtonTexts = new List<Text>();

    private EventDefinition activeEvent;

    public void ShowEvent(EventDefinition eventDefinition)
    {
        activeEvent = eventDefinition;

        if (activeEvent == null)
        {
            return;
        }

        if (titleText != null)
        {
            titleText.text = string.IsNullOrWhiteSpace(activeEvent.eventId) ? activeEvent.name : activeEvent.eventId;
        }

        if (bodyText != null)
        {
            bodyText.text = activeEvent.description;
        }

        for (int i = 0; i < choiceButtons.Count; i++)
        {
            Button button = choiceButtons[i];
            bool hasChoice = activeEvent.choices != null && i < activeEvent.choices.Count;
            button.gameObject.SetActive(hasChoice);
            button.onClick.RemoveAllListeners();

            if (!hasChoice)
            {
                continue;
            }

            int idx = i;
            button.onClick.AddListener(() => PickChoice(idx));

            if (i < choiceButtonTexts.Count && choiceButtonTexts[i] != null)
            {
                choiceButtonTexts[i].text = activeEvent.choices[i].text;
            }
        }
    }

    private void PickChoice(int choiceIndex)
    {
        if (activeEvent == null || activeEvent.choices == null || choiceIndex < 0 || choiceIndex >= activeEvent.choices.Count)
        {
            return;
        }

        eventEngine.ApplyChoice(activeEvent.choices[choiceIndex], inventory, survival);
        panelController.CloseAll();
    }
}
