// UnityEngine Shim for Standalone .NET CLI Compilation & Testing
// Tự động vô hiệu hóa khi nằm trong Unity Project (#if !UNITY_5_3_OR_NEWER)
#if !UNITY_5_3_OR_NEWER
using System;

namespace UnityEngine
{
    public struct Vector3
    {
        public float x, y, z;
        public Vector3(float x, float y, float z) { this.x = x; this.y = y; this.z = z; }
        public static Vector3 zero => new Vector3(0, 0, 0);
        public static Vector3 one => new Vector3(1, 1, 1);
        public static Vector3 forward => new Vector3(0, 0, 1);
        public static Vector3 up => new Vector3(0, 1, 0);
        public float magnitude => MathF.Sqrt(x * x + y * y + z * z);
        public Vector3 normalized => magnitude > 1e-5f ? new Vector3(x / magnitude, y / magnitude, z / magnitude) : zero;
        public static Vector3 operator +(Vector3 a, Vector3 b) => new Vector3(a.x + b.x, a.y + b.y, a.z + b.z);
        public static Vector3 operator -(Vector3 a, Vector3 b) => new Vector3(a.x - b.x, a.y - b.y, a.z - b.z);
        public static Vector3 operator *(Vector3 a, float d) => new Vector3(a.x * d, a.y * d, a.z * d);

        public static Vector3 SmoothDamp(Vector3 current, Vector3 target, ref Vector3 currentVelocity, float smoothTime, float maxSpeed, float deltaTime)
        {
            float omega = 2f / MathF.Max(0.0001f, smoothTime);
            float x = omega * deltaTime;
            float exp = 1f / (1f + x + 0.48f * x * x + 0.235f * x * x * x);
            Vector3 change = current - target;
            Vector3 temp = (currentVelocity + change * omega) * deltaTime;
            currentVelocity = (currentVelocity - temp * omega) * exp;
            return target + (change + temp) * exp;
        }

        public static Vector3 Lerp(Vector3 a, Vector3 b, float t)
        {
            t = Math.Clamp(t, 0f, 1f);
            return new Vector3(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t, a.z + (b.z - a.z) * t);
        }
    }

    public struct Quaternion
    {
        public float x, y, z, w;
        public static Quaternion identity => new Quaternion { w = 1f };
        public static Quaternion Slerp(Quaternion a, Quaternion b, float t) => b;
        public static Quaternion RotateTowards(Quaternion from, Quaternion to, float maxDegreesDelta) => to;
        public static Quaternion LookRotation(Vector3 forward, Vector3 up) => identity;
    }

    public static class Mathf
    {
        public const float PI = 3.14159265f;
        public const float Infinity = float.PositiveInfinity;
        public static float Sin(float f) => MathF.Sin(f);
        public static float Sqrt(float f) => MathF.Sqrt(f);
        public static float Clamp01(float f) => Math.Clamp(f, 0f, 1f);
        public static float Max(float a, float b) => MathF.Max(a, b);
        public static float SmoothStep(float from, float to, float t)
        {
            t = Math.Clamp(t, 0f, 1f);
            t = -2f * t * t * t + 3f * t * t;
            return to * t + from * (1f - t);
        }
        public static float Lerp(float a, float b, float t)
        {
            t = Math.Clamp(t, 0f, 1f);
            return a + (b - a) * t;
        }
    }

    public static class Random
    {
        private static readonly System.Random _rnd = new System.Random();
        public static float Range(float min, float max) => (float)(min + _rnd.NextDouble() * (max - min));
    }

    public static class Debug
    {
        public static void Log(object message) => Console.WriteLine($"[Unity Info] {message}");
        public static void LogWarning(object message) => Console.WriteLine($"[Unity Warning] {message}");
        public static void LogError(object message) => Console.WriteLine($"[Unity Error] {message}");
    }

    public class Component {}
    public class Transform : Component
    {
        public Vector3 position { get; set; } = Vector3.zero;
        public Vector3 localScale { get; set; } = Vector3.one;
        public Quaternion rotation { get; set; } = Quaternion.identity;
    }

    public class GameObject
    {
        public Transform transform { get; } = new Transform();
        public T GetComponent<T>() where T : class => null;
    }

    public class MonoBehaviour : Component
    {
        public Transform transform { get; } = new Transform();
        public GameObject gameObject { get; } = new GameObject();
        public T GetComponent<T>() where T : class => null;
    }

    public class Animator : MonoBehaviour
    {
        public int layerCount => 3;
        public void SetLayerWeight(int layerIndex, float weight) {}
    }

    public static class Time
    {
        public static float deltaTime = 0.016f; // 60 FPS
    }

    [AttributeUsage(AttributeTargets.Class | AttributeTargets.Field | AttributeTargets.Property)]
    public class RequireComponentAttribute : Attribute
    {
        public RequireComponentAttribute(Type requiredComponent) {}
    }

    [AttributeUsage(AttributeTargets.Field)]
    public class SerializeFieldAttribute : Attribute {}

    [AttributeUsage(AttributeTargets.Field)]
    public class HeaderAttribute : Attribute
    {
        public HeaderAttribute(string header) {}
    }

    public static class Camera
    {
        public class CamObj
        {
            public Transform transform = new Transform { position = new Vector3(0, 1.6f, 1.8f) };
        }
        public static CamObj main = new CamObj();
    }
}
#endif
