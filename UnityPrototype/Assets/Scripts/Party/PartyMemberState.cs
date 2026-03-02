using System;

[Serializable]
public class PartyMemberState
{
    public string name;
    public float hp = 100f;
    public bool isSick;
    public bool isInjured;
    public float morale = 50f;

    public bool IsDead => hp <= 0f;
}
