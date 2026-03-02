using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

public class PauseUI : MonoBehaviour
{
    [Header("Refs")]
    [SerializeField] private PanelController panelController;
    [SerializeField] private SaveSystem saveSystem;
    [SerializeField] private TimeSystem timeSystem;
    [SerializeField] private SurvivalComponent survival;
    [SerializeField] private PartyManager partyManager;
    [SerializeField] private ShopUI shopUI;

    [Header("UI")]
    [SerializeField] private Button resumeButton;
    [SerializeField] private Button saveButton;
    [SerializeField] private Button quitButton;

    [Header("Optional")]
    [SerializeField] private string menuSceneName = "MainMenu";

    private void OnEnable()
    {
        resumeButton.onClick.AddListener(ResumeGame);
        saveButton.onClick.AddListener(SaveGame);
        quitButton.onClick.AddListener(QuitToMenu);
    }

    private void OnDisable()
    {
        resumeButton.onClick.RemoveListener(ResumeGame);
        saveButton.onClick.RemoveListener(SaveGame);
        quitButton.onClick.RemoveListener(QuitToMenu);
    }

    private void ResumeGame()
    {
        if (GameManager.Instance != null)
        {
            GameManager.Instance.SetState(GameState.InGame);
        }

        panelController.CloseAll();
    }

    private void SaveGame()
    {
        saveSystem.Save(timeSystem, survival, partyManager, shopUI);
    }

    private void QuitToMenu()
    {
        Time.timeScale = 1f;

        if (!string.IsNullOrWhiteSpace(menuSceneName))
        {
            SceneManager.LoadScene(menuSceneName);
        }
    }
}
