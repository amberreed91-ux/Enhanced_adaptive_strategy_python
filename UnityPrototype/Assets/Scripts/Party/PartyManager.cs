using System.Collections.Generic;
using UnityEngine;

public class PartyManager : MonoBehaviour
{
    public List<PartyMemberState> members = new List<PartyMemberState>();

    public void DamageMember(int index, float amount)
    {
        if (index < 0 || index >= members.Count)
        {
            return;
        }

        PartyMemberState member = members[index];
        if (member.IsDead)
        {
            return;
        }

        member.hp = Mathf.Max(0f, member.hp - amount);
    }
}
