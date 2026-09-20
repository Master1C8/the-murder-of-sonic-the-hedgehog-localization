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

        private static string ShapeFallback(string value)
        {
            var output = new StringBuilder(value.Length);
            int position = 0;
            while (position < value.Length)
            {
                if (!IsBaseCharacter(value[position]))
                {
                    output.Append(value[position]);
                    position++;
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
            string shaped;
            if (Exact.TryGetValue(value, out shaped))
                return shaped;
            return ShapeFallback(value);
        }

        public static void SetText(TMP_Text target, string value)
        {
            target.isRightToLeftText = RightToLeft;
            target.text = Shape(value);
        }
    }
}
