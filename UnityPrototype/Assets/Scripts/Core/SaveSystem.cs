using System.IO;
using UnityEngine;

public class SaveSystem : MonoBehaviour
{
    private const string SaveFileName = "save.json";

    private string SavePath => Path.Combine(Application.persistentDataPath, SaveFileName);

    public void Save(TimeSystem timeSystem, SurvivalComponent survival, PartyManager partyManager, ShopUI shopUI)
    {
        SaveGameData data = new SaveGameData
        {
            day = timeSystem.Day,
            hour = timeSystem.Hour,
            hunger = survival.hunger,
            health = survival.health,
            money = shopUI != null ? shopUI.PlayerMoney : 0,
            party = partyManager.members
        };

        string json = JsonUtility.ToJson(data, true);
        File.WriteAllText(SavePath, json);
        Debug.Log($"Saved game to {SavePath}");
    }

    public SaveGameData Load()
    {
        if (!File.Exists(SavePath))
        {
            return null;
        }

        string json = File.ReadAllText(SavePath);
        return JsonUtility.FromJson<SaveGameData>(json);
    }
}
