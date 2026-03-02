using System;
using System.Collections.Generic;
using UnityEngine;

[CreateAssetMenu(menuName = "Game/Event Definition")]
public class EventDefinition : ScriptableObject
{
    public string eventId;
    [TextArea] public string description;
    public List<EventChoice> choices = new List<EventChoice>();
}

[Serializable]
public class EventChoice
{
    public string text;
    public int foodDelta;
    public int medicineDelta;
    public float hpDelta;
}
