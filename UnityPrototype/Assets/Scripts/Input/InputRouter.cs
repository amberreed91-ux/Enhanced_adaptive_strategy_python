using UnityEngine;
using UnityEngine.UI;

public class InputRouter : MonoBehaviour
{
    [Header("Refs")]
    [SerializeField] private Camera playerCamera;
    [SerializeField] private PanelController panelController;
    [SerializeField] private Text interactPromptText;

    [Header("Settings")]
    [SerializeField] private float interactDistance = 4f;
    [SerializeField] private LayerMask interactMask = ~0;

    private IInteractable currentInteractable;

    private void Update()
    {
        HandlePauseToggle();
        UpdateLookInteractable();
        HandleInteractKey();
    }

    private void HandlePauseToggle()
    {
        if (!Input.GetKeyDown(KeyCode.Escape))
        {
            return;
        }

        if (GameManager.Instance == null)
        {
            return;
        }

        bool isPaused = GameManager.Instance.State == GameState.Paused;

        if (isPaused)
        {
            GameManager.Instance.SetState(GameState.InGame);
            panelController.CloseAll();
        }
        else
        {
            GameManager.Instance.SetState(GameState.Paused);
            panelController.Open("Pause");
        }
    }

    private void UpdateLookInteractable()
    {
        currentInteractable = null;

        if (interactPromptText != null)
        {
            interactPromptText.text = string.Empty;
        }

        if (playerCamera == null)
        {
            return;
        }

        Ray ray = new Ray(playerCamera.transform.position, playerCamera.transform.forward);

        if (!Physics.Raycast(ray, out RaycastHit hit, interactDistance, interactMask))
        {
            return;
        }

        currentInteractable = hit.collider.GetComponentInParent<IInteractable>();
        if (currentInteractable != null && interactPromptText != null)
        {
            interactPromptText.text = "[E] " + currentInteractable.Prompt;
        }
    }

    private void HandleInteractKey()
    {
        if (!Input.GetKeyDown(KeyCode.E))
        {
            return;
        }

        if (GameManager.Instance != null && GameManager.Instance.State == GameState.Paused)
        {
            return;
        }

        currentInteractable?.Interact();
    }
}
