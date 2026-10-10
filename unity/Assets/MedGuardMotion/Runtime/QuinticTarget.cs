using System;
using UnityEngine;

namespace MedGuard.Motion
{
    // Task-space C2 interpolation, NOT a full-body inertialization solver.
    // Output must be checked for reach, overshoot, collision and contact.
    public sealed class QuinticTarget
    {
        private readonly Vector3[] c = new Vector3[6];
        private float duration;
        public void Retarget(Vector3 p0, Vector3 v0, Vector3 a0,
                             Vector3 p1, Vector3 v1, Vector3 a1, float seconds)
        {
            if (float.IsNaN(seconds) || float.IsInfinity(seconds) || seconds <= 0 ||
                !Finite(p0) || !Finite(v0) || !Finite(a0) || !Finite(p1) || !Finite(v1) || !Finite(a1))
                throw new ArgumentException("Finite boundary conditions and positive duration required.");
            duration = seconds;
            c[0] = p0; c[1] = v0 * seconds; c[2] = a0 * (.5f * seconds * seconds);
            Vector3 d = p1 - c[0] - c[1] - c[2];
            Vector3 v = v1 * seconds - c[1] - 2 * c[2];
            Vector3 a = a1 * seconds * seconds - 2 * c[2];
            c[3] = 10 * d - 4 * v + .5f * a;
            c[4] = -15 * d + 7 * v - a;
            c[5] = 6 * d - 3 * v + .5f * a;
        }
        private static bool Finite(Vector3 p) => !(float.IsNaN(p.x) || float.IsNaN(p.y) || float.IsNaN(p.z) ||
            float.IsInfinity(p.x) || float.IsInfinity(p.y) || float.IsInfinity(p.z));
        // Evaluate only while 0 <= elapsed <= duration; caller owns finished pose.
        public void Evaluate(float elapsed, out Vector3 position, out Vector3 velocity, out Vector3 acceleration)
        {
            if (duration <= 0 || float.IsNaN(elapsed) || float.IsInfinity(elapsed))
                throw new InvalidOperationException("Initialize trajectory before sampling.");
            float u = Mathf.Clamp01(elapsed / duration);
            position = c[0] + u * (c[1] + u * (c[2] + u * (c[3] + u * (c[4] + u * c[5]))));
            velocity = (c[1] + u * (2 * c[2] + u * (3 * c[3] + u * (4 * c[4] + u * 5 * c[5])))) / duration;
            acceleration = (2 * c[2] + u * (6 * c[3] + u * (12 * c[4] + u * 20 * c[5]))) / (duration * duration);
        }
    }
}
