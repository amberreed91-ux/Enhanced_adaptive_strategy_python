using UnityEngine;

public class SurvivalComponent : MonoBehaviour
{
    [Range(0f, 100f)] public float hunger = 100f;
    [Range(0f, 100f)] public float health = 100f;

    [SerializeField] private float hungerDrainPerHour = 3f;
    [SerializeField] private float healthLossWhenStarvingPerHour = 8f;

    private TimeSystem timeSystem;
    private float lastHour;

    private void Start()
    {
        timeSystem = FindObjectOfType<TimeSystem>();
        if (timeSystem != null)
        {
            lastHour = timeSystem.Hour;
        }
    }

    private void Update()
    {
        if (timeSystem == null)
        {
            return;
        }

        float deltaHours = Mathf.Abs(timeSystem.Hour - lastHour);
        if (deltaHours > 12f)
        {
            deltaHours = 24f - deltaHours;
        }

        lastHour = timeSystem.Hour;

        hunger = Mathf.Max(0f, hunger - hungerDrainPerHour * deltaHours);

        if (hunger <= 0f)
        {
            health = Mathf.Max(0f, health - healthLossWhenStarvingPerHour * deltaHours);
        }
    }
}
