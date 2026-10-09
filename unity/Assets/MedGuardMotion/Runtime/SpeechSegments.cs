using System;
using System.Collections.Generic;
using System.Text.RegularExpressions;

namespace MedGuard.Motion
{
    public static class SpeechSegments
    {
        // The backend's prepared first segment has the same boundary rule.
        // A decimal such as 38.5 does not contain punctuation followed by space.
        public static string First(string text, int limit = 180)
        {
            if (limit < 1) throw new ArgumentOutOfRangeException(nameof(limit));
            string clean = Regex.Replace(text ?? "", @"\s+", " ").Trim();
            Match boundary = Regex.Match(clean, @"[.!?](?=\s|$)");
            int end = boundary.Success ? boundary.Index + 1 : clean.Length;
            if (end > limit)
            {
                int space = clean.LastIndexOf(' ', Math.Min(limit, clean.Length - 1));
                end = space > 0 ? space : limit;
            }
            return clean.Substring(0, end).Trim();
        }
        public static string[] Split(string text)
        {
            var chunks = new List<string>();
            string remaining = Regex.Replace(text ?? "", @"\s+", " ").Trim();
            bool first = true;
            while (remaining.Length > 0)
            {
                string segment = First(remaining, first ? 180 : 360);
                chunks.Add(segment); remaining = remaining.Substring(segment.Length).TrimStart(); first = false;
            }
            return chunks.ToArray();
        }
    }
}
