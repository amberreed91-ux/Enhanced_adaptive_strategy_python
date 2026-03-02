using UnityEngine;

public class EventInteractable : MonoBehaviour, IInteractable
{
    [SerializeField] private PanelController panelController;
    [SerializeField] private EventUI eventUI;
    [SerializeField] private EventDefinition[] possibleEvents;
    [SerializeField] private bool oneShot = true;

    private bool used;

    public string Prompt => "Investigate";

    public void Interact()
    {
        if (oneShot && used)
        {
            return;
        }

        if (possibleEvents == null || possibleEvents.Length == 0)
        {
            return;
        }

        EventDefinition picked = possibleEvents[Random.Range(0, possibleEvents.Length)];

        panelController.Open("Event");
        eventUI.ShowEvent(picked);

        used = true;
    }
}
