using UnityEngine;

public class PlayerStateLock : MonoBehaviour
{
    [Header("Refs")]
    [SerializeField] private PanelController panelController;
    [SerializeField] private MonoBehaviour movementController;
    [SerializeField] private MonoBehaviour lookController;

    [Header("Cursor")]
    [SerializeField] private bool lockCursorWhenGameplay = true;

    private void Update()
    {
        bool isBlocked = panelController != null && panelController.AnyOpen();

        if (movementController != null)
        {
            movementController.enabled = !isBlocked;
        }

        if (lookController != null)
        {
            lookController.enabled = !isBlocked;
        }

        if (!lockCursorWhenGameplay)
        {
            return;
        }

        Cursor.visible = isBlocked;
        Cursor.lockState = isBlocked ? CursorLockMode.None : CursorLockMode.Locked;
    }
}
