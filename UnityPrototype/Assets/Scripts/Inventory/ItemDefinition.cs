using UnityEngine;

[CreateAssetMenu(menuName = "Game/Item Definition")]
public class ItemDefinition : ScriptableObject
{
    public string itemId;
    public string displayName;
    public float weight = 1f;
    public int maxStack = 99;
    public int baseValue = 1;
}
