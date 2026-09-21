using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Runtime.InteropServices;
using System.Text;
using TMPro;
using UnityEngine;

namespace VNRevival
{
    public static class Runtime
    {
        private sealed class Translation
        {
            public string Context;
            public string Value;
            public float FontSize;
        }

        private const uint FR_PRIVATE = 0x10;
        private const string PackageDirectory = "VNRevival";
        private static readonly Dictionary<string, List<Translation>> Translations =
            new Dictionary<string, List<Translation>>(StringComparer.Ordinal);
        private static readonly Dictionary<string, string> ExactShapes =
            new Dictionary<string, string>(StringComparer.Ordinal);
        private static readonly Dictionary<string, string> SpanShapes =
            new Dictionary<string, string>(StringComparer.Ordinal);
        private static readonly Dictionary<int, string> LastRenderedValues =
            new Dictionary<int, string>();
        private static bool loadAttempted;
        private static bool loaded;
        private static bool initialized;
        private static int mode;
        private static bool rightToLeft;
        private static string locale;
        private static string packageRoot;
        private static string fontFile;
        private static string fontFamily;
        private static TMP_FontAsset runtimeFont;

        [DllImport("gdi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern int AddFontResourceEx(string filename, uint flags, IntPtr reserved);

        private static string Decode(string value)
        {
            return Encoding.UTF8.GetString(Convert.FromBase64String(value));
        }

        private static StreamReader OpenGzipText(string path)
        {
            return new StreamReader(
                new GZipStream(File.OpenRead(path), CompressionMode.Decompress),
                new UTF8Encoding(false, true)
            );
        }

        private static void AddTranslation(string source, string context, string value, float fontSize)
        {
            List<Translation> rows;
            if (!Translations.TryGetValue(source, out rows))
            {
                rows = new List<Translation>();
                Translations.Add(source, rows);
            }
            rows.Add(new Translation { Context = context, Value = value, FontSize = fontSize });
        }

        private static bool EnsureLoaded()
        {
            if (loadAttempted)
                return loaded;
            loadAttempted = true;
            try
            {
                packageRoot = Path.Combine(Application.streamingAssetsPath, PackageDirectory);
                string activePath = Path.Combine(packageRoot, "active-locale.txt");
                locale = File.ReadAllText(activePath, new UTF8Encoding(false, true)).Trim();
                if (locale.Length == 0 || locale.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0)
                    throw new InvalidDataException("The active VN Revival locale is invalid");
                string dataPath = Path.Combine(Path.Combine(packageRoot, "Locales"), locale + ".runtime.tsv.gz");
                using (StreamReader reader = OpenGzipText(dataPath))
                {
                    string header = reader.ReadLine();
                    string[] fields = header == null ? new string[0] : header.Split('\t');
                    if (fields.Length != 6 || fields[0] != "VNREVIVAL2" || fields[1] != locale)
                        throw new InvalidDataException("The VN Revival runtime-data header is invalid");
                    mode = Int32.Parse(fields[2], CultureInfo.InvariantCulture);
                    rightToLeft = fields[3] == "1";
                    fontFile = Decode(fields[4]);
                    fontFamily = Decode(fields[5]);
                    string line;
                    while ((line = reader.ReadLine()) != null)
                    {
                        if (line.Length == 0)
                            continue;
                        fields = line.Split('\t');
                        if (fields.Length == 5 && fields[0] == "T")
                        {
                            float fontSize = fields[4].Length == 0
                                ? 0f
                                : Single.Parse(fields[4], CultureInfo.InvariantCulture);
                            AddTranslation(Decode(fields[1]), Decode(fields[2]), Decode(fields[3]), fontSize);
                        }
                        else if (fields.Length == 3 && (fields[0] == "E" || fields[0] == "S"))
                        {
                            Dictionary<string, string> target = fields[0] == "E" ? ExactShapes : SpanShapes;
                            string logical = Decode(fields[1]);
                            string shaped = Decode(fields[2]);
                            string previous;
                            if (target.TryGetValue(logical, out previous) && previous != shaped)
                                throw new InvalidDataException("Conflicting VN Revival shaping entry");
                            target[logical] = shaped;
                        }
                        else
                        {
                            throw new InvalidDataException("The VN Revival runtime-data row is invalid");
                        }
                    }
                }
                loaded = true;
            }
            catch (Exception exception)
            {
                Debug.LogError("VN Revival localization could not be loaded: " + exception);
                loaded = false;
            }
            return loaded;
        }

        private static string TransformPath(TMP_Text target)
        {
            if (target == null || target.transform == null)
                return String.Empty;
            var names = new List<string>();
            Transform cursor = target.transform;
            while (cursor != null)
            {
                names.Add(cursor.name);
                cursor = cursor.parent;
            }
            names.Reverse();
            return String.Join("/", names.ToArray());
        }

        private static Translation SelectTranslation(string source, TMP_Text target)
        {
            List<Translation> rows;
            if (!Translations.TryGetValue(source, out rows) || rows.Count == 0)
                return null;
            if (rows.Count == 1)
                return rows[0];
            string path = TransformPath(target);
            Translation best = null;
            int bestScore = -1;
            foreach (Translation row in rows)
            {
                if (String.IsNullOrEmpty(row.Context))
                    continue;
                int score = path.Equals(row.Context, StringComparison.Ordinal) ? row.Context.Length + 10000 :
                    path.EndsWith(row.Context, StringComparison.Ordinal) ? row.Context.Length : -1;
                if (score > bestScore)
                {
                    best = row;
                    bestScore = score;
                }
            }
            return best ?? rows[0];
        }

        private static void EnsureRuntimeFont()
        {
            if (runtimeFont != null || !EnsureLoaded())
                return;
            try
            {
                string path = Path.Combine(Path.Combine(packageRoot, "Fonts"), fontFile);
                if (!File.Exists(path))
                    throw new FileNotFoundException("The VN Revival locale font is missing", path);
                if (Application.platform == RuntimePlatform.WindowsPlayer)
                {
                    if (AddFontResourceEx(path, FR_PRIVATE, IntPtr.Zero) == 0)
                        throw new InvalidOperationException("Windows rejected the private VN Revival font");
                }
                Font source = Font.CreateDynamicFontFromOSFont(fontFamily, 90);
                if (source == null)
                    throw new InvalidOperationException("Unity could not create the VN Revival dynamic font");
                runtimeFont = TMP_FontAsset.CreateFontAsset(source);
                if (runtimeFont == null)
                    throw new InvalidOperationException("TextMesh Pro could not create the VN Revival font asset");
                runtimeFont.name = "VN Revival " + locale;
            }
            catch (Exception exception)
            {
                Debug.LogError("VN Revival font could not be loaded: " + exception);
            }
        }

        public static void Initialize()
        {
            if (initialized)
                return;
            initialized = true;
            if (!EnsureLoaded())
                return;
            EnsureRuntimeFont();
            var root = new GameObject("VN Revival Localization Runtime");
            UnityEngine.Object.DontDestroyOnLoad(root);
            root.AddComponent<RuntimeDriver>();
            LocalizeAll();
        }

        public static string LoadStory(string source)
        {
            if (!EnsureLoaded())
                return source;
            try
            {
                string path = Path.Combine(Path.Combine(packageRoot, "Locales"), locale + ".story.json.gz");
                using (StreamReader reader = OpenGzipText(path))
                    return reader.ReadToEnd();
            }
            catch (Exception exception)
            {
                Debug.LogError("VN Revival story could not be loaded: " + exception);
                return source;
            }
        }

        public static void LocalizeAll()
        {
            if (!EnsureLoaded())
                return;
            EnsureRuntimeFont();
            TMP_Text[] labels = Resources.FindObjectsOfTypeAll<TMP_Text>();
            foreach (TMP_Text label in labels)
            {
                if (label != null)
                    SetText(label, label.text);
            }
        }

        public static void SetText(TMP_Text target, string value)
        {
            if (target == null)
                return;
            if (!EnsureLoaded())
            {
                target.text = value;
                return;
            }
            int instanceId = target.GetInstanceID();
            string lastRendered;
            bool alreadyLocalized = LastRenderedValues.TryGetValue(instanceId, out lastRendered)
                && lastRendered == value;
            Translation row = alreadyLocalized ? null : SelectTranslation(value, target);
            string logical = row == null ? value : row.Value;
            if (row != null && row.FontSize > 0f)
                target.fontSize = row.FontSize;
            EnsureRuntimeFont();
            if (runtimeFont != null)
            {
                TMP_FontAsset primary = target.font;
                if (primary == null)
                {
                    target.font = runtimeFont;
                }
                else if (primary != runtimeFont)
                {
                    List<TMP_FontAsset> fallbacks = primary.fallbackFontAssetTable;
                    if (fallbacks == null)
                    {
                        fallbacks = new List<TMP_FontAsset>();
                        primary.fallbackFontAssetTable = fallbacks;
                    }
                    if (!fallbacks.Contains(runtimeFont))
                        fallbacks.Add(runtimeFont);
                }
            }
            target.isRightToLeftText = RequiresRightToLeft(logical);
            string rendered = Shape(logical);
            target.text = rendered;
            LastRenderedValues[instanceId] = rendered;
        }

        private static bool IsBaseCharacter(char value)
        {
            int codepoint = value;
            switch (mode)
            {
                case 1:
                    return (codepoint >= 0x0600 && codepoint <= 0x06FF)
                        || (codepoint >= 0x0750 && codepoint <= 0x077F)
                        || (codepoint >= 0x08A0 && codepoint <= 0x08FF);
                case 2:
                    return codepoint >= 0x0590 && codepoint <= 0x05FF;
                case 3:
                    return (codepoint >= 0x0900 && codepoint <= 0x097F)
                        || (codepoint >= 0xA8E0 && codepoint <= 0xA8FF);
                case 4:
                    return codepoint >= 0x0E00 && codepoint <= 0x0E7F;
                default:
                    return false;
            }
        }

        private static bool IsJoinerOrMark(char value)
        {
            if (value == '\u200C' || value == '\u200D')
                return true;
            UnicodeCategory category = CharUnicodeInfo.GetUnicodeCategory(value);
            return category == UnicodeCategory.NonSpacingMark
                || category == UnicodeCategory.SpacingCombiningMark
                || category == UnicodeCategory.EnclosingMark;
        }

        private static bool IsPreparedScriptCharacter(char value)
        {
            return value >= '\uE000' && value <= '\uF8FF';
        }

        private static bool ContainsPreparedScript(string value)
        {
            foreach (char character in value)
                if (IsPreparedScriptCharacter(character))
                    return true;
            return false;
        }

        private static bool ContainsLtrContent(string value)
        {
            foreach (char character in value)
            {
                if ((character >= 'A' && character <= 'Z')
                    || (character >= 'a' && character <= 'z')
                    || (character >= '0' && character <= '9'))
                    return true;
            }
            return false;
        }

        private static string CompensateLtrRun(string value)
        {
            if (!rightToLeft || !ContainsLtrContent(value))
                return value;
            int start = 0;
            while (start < value.Length && Char.IsWhiteSpace(value[start]))
                start++;
            int end = value.Length;
            while (end > start && Char.IsWhiteSpace(value[end - 1]))
                end--;
            char[] characters = value.Substring(start, end - start).ToCharArray();
            Array.Reverse(characters);
            return value.Substring(0, start) + new string(characters) + value.Substring(end);
        }

        private static bool TryReadKnownTmpTag(string value, int position, out int tagEnd)
        {
            tagEnd = -1;
            if (position >= value.Length || value[position] != '<')
                return false;
            int end = value.IndexOf('>', position + 1);
            if (end < 0)
                return false;
            string body = value.Substring(position + 1, end - position - 1);
            if (body.StartsWith("/", StringComparison.Ordinal))
                body = body.Substring(1);
            int equals = body.IndexOf('=');
            string name = equals >= 0 ? body.Substring(0, equals) : body;
            if (!name.Equals("style", StringComparison.OrdinalIgnoreCase)
                && !name.Equals("size", StringComparison.OrdinalIgnoreCase)
                && !name.Equals("color", StringComparison.OrdinalIgnoreCase)
                && !name.Equals("i", StringComparison.OrdinalIgnoreCase)
                && !name.Equals("br", StringComparison.OrdinalIgnoreCase))
                return false;
            tagEnd = end;
            return true;
        }

        private static string ShapeFallback(string value)
        {
            var output = new StringBuilder(value.Length);
            int position = 0;
            while (position < value.Length)
            {
                int tagEnd;
                if (TryReadKnownTmpTag(value, position, out tagEnd))
                {
                    output.Append(value.Substring(position, tagEnd - position + 1));
                    position = tagEnd + 1;
                    continue;
                }
                if (!IsBaseCharacter(value[position]))
                {
                    int runEnd = position + 1;
                    while (runEnd < value.Length
                        && (value[runEnd] != '<' || !TryReadKnownTmpTag(value, runEnd, out tagEnd))
                        && !IsBaseCharacter(value[runEnd]))
                        runEnd++;
                    output.Append(CompensateLtrRun(value.Substring(position, runEnd - position)));
                    position = runEnd;
                    continue;
                }
                int end = position + 1;
                while (end < value.Length && (IsBaseCharacter(value[end]) || IsJoinerOrMark(value[end])))
                    end++;
                string span = value.Substring(position, end - position);
                string shaped;
                if (SpanShapes.TryGetValue(span, out shaped))
                {
                    output.Append(shaped);
                    position = end;
                    continue;
                }
                int cursor = position;
                while (cursor < end)
                {
                    bool matched = false;
                    for (int candidateEnd = end; candidateEnd > cursor; candidateEnd--)
                    {
                        string candidate = value.Substring(cursor, candidateEnd - cursor);
                        if (!SpanShapes.TryGetValue(candidate, out shaped))
                            continue;
                        output.Append(shaped);
                        cursor = candidateEnd;
                        matched = true;
                        break;
                    }
                    if (!matched)
                        output.Append(value[cursor++]);
                }
                position = end;
            }
            return output.ToString();
        }

        private static string Shape(string value)
        {
            if (String.IsNullOrEmpty(value) || !EnsureLoaded())
                return value;
            if (rightToLeft && ContainsPreparedScript(value))
                return value;
            if (rightToLeft && !RequiresRightToLeft(value))
                return value;
            string shaped;
            return ExactShapes.TryGetValue(value, out shaped) ? shaped : ShapeFallback(value);
        }

        private static bool RequiresRightToLeft(string value)
        {
            if (!rightToLeft || String.IsNullOrEmpty(value))
                return false;
            foreach (char character in value)
                if (IsBaseCharacter(character) || IsPreparedScriptCharacter(character))
                    return true;
            return false;
        }

        public static bool ShouldCompleteTextAnimation(
            float now,
            float startedAt,
            int characterCount,
            float letterDelay,
            float duration,
            bool skipCalled
        )
        {
            return skipCalled
                || characterCount <= 0
                || now >= startedAt + ((characterCount - 1) * letterDelay) + duration;
        }
    }

    public sealed class RuntimeDriver : MonoBehaviour
    {
        private float nextRefresh;

        private void Update()
        {
            if (Time.unscaledTime < nextRefresh)
                return;
            nextRefresh = Time.unscaledTime + 0.5f;
            Runtime.LocalizeAll();
        }
    }
}
