using System;
using System.Collections.Generic;

[Serializable]
public class SaveGameData
{
    public int day;
    public float hour;
    public float hunger;
    public float health;
    public int money;
    public List<PartyMemberState> party;
}
