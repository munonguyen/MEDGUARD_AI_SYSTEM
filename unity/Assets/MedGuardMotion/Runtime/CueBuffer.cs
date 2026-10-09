using System;
using System.Collections.Generic;

namespace MedGuard.Motion
{
    [Serializable]
    public struct GestureCue
    {
        public int generationId;
        public string speechId, eventId, gestureId;
        public double prepareAt, strokeAt, releaseAt, endAt;
    }
    // Stylistic cues only. Cancel and alert-control events must not wait here.
    // Native reference; invoke from main-thread planning, NOT a network callback.
    public sealed class CueBuffer
    {
        private readonly GestureCue[] items;
        private readonly HashSet<string> seen = new HashSet<string>();
        private int count, generation;
        private string speech;
        private bool active;
        public int Count => count;
        public CueBuffer(int capacity = 128)
        {
            if (capacity < 1 || capacity > 1024) throw new ArgumentOutOfRangeException(nameof(capacity));
            items = new GestureCue[capacity];
        }
        public bool BeginGeneration(int nextGeneration, string speechId)
        {
            if (nextGeneration <= generation || string.IsNullOrEmpty(speechId)) return false;
            generation = nextGeneration; speech = speechId; active = true;
            Array.Clear(items, 0, count); count = 0; seen.Clear(); return true;
        }
        public void Cancel()
        {
            active = false; Array.Clear(items, 0, count); count = 0; seen.Clear();
        }
        static bool Finite(double x) => !double.IsNaN(x) && !double.IsInfinity(x);
        public bool TryEnqueue(GestureCue cue, double contentNow)
        {
            if (!active || cue.generationId != generation || cue.speechId != speech ||
                string.IsNullOrEmpty(cue.eventId) || string.IsNullOrEmpty(cue.gestureId) ||
                !Finite(contentNow) || contentNow < 0 || !Finite(cue.prepareAt) || !Finite(cue.strokeAt) ||
                !Finite(cue.releaseAt) || !Finite(cue.endAt) || cue.prepareAt < 0 ||
                cue.prepareAt > cue.strokeAt || cue.strokeAt > cue.releaseAt || cue.releaseAt >= cue.endAt ||
                cue.endAt <= contentNow || cue.prepareAt - contentNow > 10 || seen.Contains(cue.eventId) ||
                seen.Count >= 1024 || count == items.Length) return false;
            int index = count;
            while (index > 0 && items[index - 1].prepareAt > cue.prepareAt)
            { items[index] = items[index - 1]; index--; }
            items[index] = cue; count++; seen.Add(cue.eventId); return true;
        }
        public bool TryTakeDue(double contentNow, out GestureCue cue)
        {
            cue = default;
            if (!active || !Finite(contentNow)) return false;
            while (count > 0 && items[0].endAt <= contentNow) RemoveFirst();
            if (count == 0 || items[0].prepareAt > contentNow) return false;
            cue = items[0]; RemoveFirst(); return true;
        }
        private void RemoveFirst()
        {
            Array.Copy(items, 1, items, 0, --count); items[count] = default;
        }
    }
}
