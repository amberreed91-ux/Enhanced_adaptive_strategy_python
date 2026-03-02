using UnityEngine;

public class CampInteractable : MonoBehaviour, IInteractable
{
    [SerializeField] private PanelController panelController;

    public string Prompt => "Use Camp";

    public void Interact()
    {
        panelController.Open("Camp");
    }
}
