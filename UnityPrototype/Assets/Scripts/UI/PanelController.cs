using System.Collections.Generic;
using UnityEngine;

public class PanelController : MonoBehaviour
{
    [System.Serializable]
    public class PanelEntry
    {
        public string id;
        public GameObject panel;
    }

    [SerializeField] private List<PanelEntry> panels = new List<PanelEntry>();

    private readonly Dictionary<string, GameObject> panelMap = new Dictionary<string, GameObject>();

    private void Awake()
    {
        panelMap.Clear();

        for (int i = 0; i < panels.Count; i++)
        {
            PanelEntry panel = panels[i];
            if (panel.panel == null || string.IsNullOrWhiteSpace(panel.id))
            {
                continue;
            }

            panelMap[panel.id] = panel.panel;
            panel.panel.SetActive(false);
        }
    }

    public void Open(string panelId)
    {
        CloseAll();
        if (panelMap.TryGetValue(panelId, out GameObject panel))
        {
            panel.SetActive(true);
        }
    }

    public void CloseAll()
    {
        foreach (KeyValuePair<string, GameObject> entry in panelMap)
        {
            entry.Value.SetActive(false);
        }
    }

    public bool IsOpen(string panelId)
    {
        if (!panelMap.TryGetValue(panelId, out GameObject panel))
        {
            return false;
        }

        return panel.activeSelf;
    }

    public bool AnyOpen()
    {
        foreach (KeyValuePair<string, GameObject> entry in panelMap)
        {
            if (entry.Value.activeSelf)
            {
                return true;
            }
        }

        return false;
    }
}
