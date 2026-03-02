using UnityEngine;

public class SettlementInteractable : MonoBehaviour, IInteractable
{
    [SerializeField] private PanelController panelController;

    public string Prompt => "Trade";

    public void Interact()
    {
        panelController.Open("Shop");
    }
}
