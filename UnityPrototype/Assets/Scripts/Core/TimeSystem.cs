using System;
using UnityEngine;

public class TimeSystem : MonoBehaviour
{
    [SerializeField] private float gameMinutesPerRealSecond = 5f;

    public int Day { get; private set; } = 1;
    public float Hour { get; private set; } = 8f;

    public event Action<int> OnDayChanged;
    public event Action<float> OnHourChanged;

    private void Update()
    {
        float gameMinutes = Time.deltaTime * gameMinutesPerRealSecond;
        AdvanceHours(gameMinutes / 60f);
    }

    public void AdvanceHours(float hours)
    {
        if (hours <= 0f)
        {
            return;
        }

        Hour += hours;

        while (Hour >= 24f)
        {
            Hour -= 24f;
            Day++;
            OnDayChanged?.Invoke(Day);
        }

        OnHourChanged?.Invoke(Hour);
    }

    public void SetTime(int day, float hour)
    {
        Day = Mathf.Max(1, day);
        Hour = Mathf.Repeat(hour, 24f);
        OnHourChanged?.Invoke(Hour);
    }
}
