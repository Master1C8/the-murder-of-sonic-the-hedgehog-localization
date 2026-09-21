using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Text;
using TMPro;

namespace VNRevival
{
    public static class TextShaper
    {
        private static readonly Dictionary<string, string> Exact =
            new Dictionary<string, string>(StringComparer.Ordinal);
        private static readonly Dictionary<string, string> Spans =
            new Dictionary<string, string>(StringComparer.Ordinal);
        private static readonly int Mode;
        private static readonly bool RightToLeft;

        static TextShaper()
        {
            Stream stream = Assembly.GetExecutingAssembly().GetManifestResourceStream(
                "VNRevival.ShapingMap"
            );
            if (stream == null)
                throw new InvalidDataException("VN Revival shaping map resource is missing");
            using (stream)
            using (var reader = new StreamReader(stream, new UTF8Encoding(false, true)))
            {
                string header = reader.ReadLine();
                string[] headerFields = header == null ? new string[0] : header.Split('\t');
                if (headerFields.Length != 3 || headerFields[0] != "VNREVIVAL1")
                    throw new InvalidDataException("VN Revival shaping map header is invalid");
                Mode = Int32.Parse(headerFields[1], CultureInfo.InvariantCulture);
                RightToLeft = headerFields[2] == "1";
                string line;
                while ((line = reader.ReadLine()) != null)
                {
                    if (String.IsNullOrWhiteSpace(line))
                        continue;
                    string[] fields = line.Split('\t');
                    if (fields.Length != 3 || (fields[0] != "E" && fields[0] != "S"))
                        throw new InvalidDataException("VN Revival shaping map row is invalid");
                    string logical = Decode(fields[1]);
                    string shaped = Decode(fields[2]);
                    Dictionary<string, string> target = fields[0] == "E" ? Exact : Spans;
                    target.Add(logical, shaped);
                }
            }
        }

        private static string Decode(string value)
        {
            return Encoding.UTF8.GetString(Convert.FromBase64String(value));
        }

        private static bool IsBaseCharacter(char value)
        {
            int codepoint = value;
            switch (Mode)
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
            // Build-time HarfBuzz shaping stores contextual glyph instances in
            // the BMP private-use area. Those values no longer carry Arabic or
            // Hebrew Unicode bidi classes, so recognize them explicitly.
            return value >= '\uE000' && value <= '\uF8FF';
        }

        private static bool ContainsPreparedScript(string value)
        {
            foreach (char character in value)
            {
                if (IsPreparedScriptCharacter(character))
                    return true;
            }
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
            if (!RightToLeft || !ContainsLtrContent(value))
                return value;
            int start = 0;
            while (start < value.Length && Char.IsWhiteSpace(value[start]))
                start++;
            int end = value.Length;
            while (end > start && Char.IsWhiteSpace(value[end - 1]))
                end--;
            char[] characters = value.Substring(start, end - start).ToCharArray();
            Array.Reverse(characters);
            return value.Substring(0, start)
                + new string(characters)
                + value.Substring(end);
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
                // TMP must receive rich-text tags byte-for-byte. Reversing the
                // Latin characters inside a tag makes the parser render the
                // markup literally (for example, <style=CarName>).
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
                        && (value[runEnd] != '<'
                            || !TryReadKnownTmpTag(value, runEnd, out tagEnd))
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
                if (Spans.TryGetValue(span, out shaped))
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
                        if (!Spans.TryGetValue(candidate, out shaped))
                            continue;
                        output.Append(shaped);
                        cursor = candidateEnd;
                        matched = true;
                        break;
                    }
                    if (!matched)
                    {
                        output.Append(value[cursor]);
                        cursor++;
                    }
                }
                position = end;
            }
            return output.ToString();
        }

        public static string Shape(string value)
        {
            if (String.IsNullOrEmpty(value))
                return value;
            // Serialized UI and inventory fields may already contain shaped
            // PUA glyphs. Never shape or compensate those strings a second
            // time; SetText still enables RTL so TMP performs its one intended
            // visual reversal and restores pre-compensated Latin runs.
            if (RightToLeft && ContainsPreparedScript(value))
                return value;
            // Pure-LTR dynamic values (player names, dates, timestamps) must
            // not be pre-reversed when the locale itself is RTL. Compensation
            // is required only for a mixed value that will actually enable
            // TMP's RTL mode.
            if (RightToLeft && !RequiresRightToLeft(value))
                return value;
            string shaped;
            if (Exact.TryGetValue(value, out shaped))
                return shaped;
            return ShapeFallback(value);
        }

        private static bool RequiresRightToLeft(string value)
        {
            if (!RightToLeft || String.IsNullOrEmpty(value))
                return false;
            foreach (char character in value)
            {
                if (IsBaseCharacter(character) || IsPreparedScriptCharacter(character))
                    return true;
            }
            return false;
        }

        public static void SetText(TMP_Text target, string value)
        {
            // Dynamic save metadata can stay Latin even in an RTL locale
            // (player names and Unity's English DateTime formatting). TMP's
            // RTL switch reverses those LTR-only values character-by-character,
            // so enable it only when this particular value contains script
            // characters that actually require RTL layout.
            target.isRightToLeftText = RequiresRightToLeft(value);
            target.text = Shape(value);
        }
    }
}
