using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using Mono.Cecil;
using Mono.Cecil.Cil;

internal static class PatchManagedStrings
{
    private sealed class Patch
    {
        public string TypeName;
        public string MethodName;
        public int Offset;
        public string Source;
        public string Translation;
        public bool Applied;
    }

    private sealed class DisplayLabel
    {
        public string RuntimeKey;
        public string Translation;
    }

    private static IEnumerable<TypeDefinition> WalkTypes(IEnumerable<TypeDefinition> roots)
    {
        foreach (TypeDefinition type in roots)
        {
            yield return type;
            foreach (TypeDefinition nested in WalkTypes(type.NestedTypes))
                yield return nested;
        }
    }

    private static string Decode(string value)
    {
        return Encoding.UTF8.GetString(Convert.FromBase64String(value));
    }

    private static MethodDefinition AddDisplayLabelMethod(
        ModuleDefinition module,
        TypeDefinition helperType,
        string methodName,
        string parameterName,
        IList<DisplayLabel> labels
    )
    {
        var method = new MethodDefinition(
            methodName,
            MethodAttributes.Static | MethodAttributes.Assembly | MethodAttributes.HideBySig,
            module.TypeSystem.String
        );
        method.Parameters.Add(new ParameterDefinition(parameterName, ParameterAttributes.None, module.TypeSystem.String));
        MethodReference stringEquality = module.ImportReference(
            typeof(string).GetMethod("op_Equality", new Type[] { typeof(string), typeof(string) })
        );
        ILProcessor il = method.Body.GetILProcessor();
        foreach (DisplayLabel label in labels)
        {
            Instruction next = il.Create(OpCodes.Nop);
            il.Append(il.Create(OpCodes.Ldarg_0));
            il.Append(il.Create(OpCodes.Ldstr, label.RuntimeKey));
            il.Append(il.Create(OpCodes.Call, stringEquality));
            il.Append(il.Create(OpCodes.Brfalse, next));
            il.Append(il.Create(OpCodes.Ldstr, label.Translation));
            il.Append(il.Create(OpCodes.Ret));
            il.Append(next);
        }
        il.Append(il.Create(OpCodes.Ldarg_0));
        il.Append(il.Create(OpCodes.Ret));
        helperType.Methods.Add(method);
        return method;
    }

    private static TypeDefinition AddDisplayLabelsType(ModuleDefinition module)
    {
        var helperType = new TypeDefinition(
            "VNRevival",
            "DisplayLabels",
            TypeAttributes.Class | TypeAttributes.Abstract | TypeAttributes.Sealed | TypeAttributes.NotPublic,
            module.TypeSystem.Object
        );
        module.Types.Add(helperType);
        return helperType;
    }

    private static void RedirectSpeakerDisplay(
        AssemblyDefinition assembly,
        MethodDefinition translateSpeaker
    )
    {
        TypeDefinition dialogView = WalkTypes(assembly.MainModule.Types)
            .Single(item => item.Name == "DialogView");
        MethodDefinition target = dialogView.Methods.Single(
            item => item.Name == "OnDialogReadyToUpdate" && item.HasBody
        );
        var matches = target.Body.Instructions.Where(instruction => {
            MethodReference called = instruction.Operand as MethodReference;
            Instruction argument = instruction.Previous;
            Instruction fieldLoad = argument == null ? null : argument.Previous;
            FieldReference field = fieldLoad == null ? null : fieldLoad.Operand as FieldReference;
            return instruction.OpCode == OpCodes.Callvirt
                && called != null
                && called.Name == "set_text"
                && argument != null
                && argument.OpCode == OpCodes.Ldarg_1
                && fieldLoad != null
                && fieldLoad.OpCode == OpCodes.Ldfld
                && field != null
                && field.Name == "nameTagText";
        }).ToList();
        if (matches.Count != 1)
            throw new InvalidDataException("Expected one direct speaker-to-nameTagText assignment");
        target.Body.GetILProcessor().InsertBefore(
            matches[0],
            Instruction.Create(OpCodes.Call, translateSpeaker)
        );
    }

    private static void RedirectSaveLocationDisplay(
        AssemblyDefinition assembly,
        MethodDefinition translateSaveLocation
    )
    {
        TypeDefinition saveFileView = WalkTypes(assembly.MainModule.Types)
            .Single(item => item.Name == "SaveFileView");
        MethodDefinition target = saveFileView.Methods.Single(
            item => item.Name == "UpdateInfoText" && item.HasBody
        );
        var matches = target.Body.Instructions.Where(instruction => {
            MethodReference called = instruction.Operand as MethodReference;
            if (instruction.OpCode != OpCodes.Callvirt || called == null || called.Name != "set_text")
                return false;
            Instruction cursor = instruction.Previous;
            for (int distance = 0; cursor != null && distance < 10; distance++, cursor = cursor.Previous)
            {
                FieldReference field = cursor.Operand as FieldReference;
                if (cursor.OpCode == OpCodes.Ldfld && field != null && field.Name == "_locationName")
                    return true;
            }
            return false;
        }).ToList();
        if (matches.Count != 2)
            throw new InvalidDataException(
                String.Format(
                    CultureInfo.InvariantCulture,
                    "Expected two save-location text assignments; found {0}",
                    matches.Count
                )
            );
        ILProcessor il = target.Body.GetILProcessor();
        foreach (Instruction match in matches)
            il.InsertBefore(match, Instruction.Create(OpCodes.Call, translateSaveLocation));
    }

    private static List<DisplayLabel> ReadDisplayLabels(string path, string description)
    {
        var labels = new List<DisplayLabel>();
        foreach (string line in File.ReadAllLines(path, Encoding.UTF8))
        {
            if (String.IsNullOrWhiteSpace(line))
                continue;
            string[] fields = line.Split('\t');
            if (fields.Length != 2)
                throw new InvalidDataException("Malformed " + description + " line");
            labels.Add(new DisplayLabel {
                RuntimeKey = Decode(fields[0]),
                Translation = Decode(fields[1]),
            });
        }
        if (labels.Any(item => String.IsNullOrEmpty(item.RuntimeKey) || String.IsNullOrEmpty(item.Translation)))
            throw new InvalidDataException(description + " entries must not be empty");
        if (labels.Select(item => item.RuntimeKey).Distinct(StringComparer.Ordinal).Count() != labels.Count)
            throw new InvalidDataException("Duplicate " + description + " runtime key");
        return labels;
    }

    private static int RedirectAllTextAssignments(
        AssemblyDefinition assembly,
        string shaperAssemblyPath
    )
    {
        AssemblyDefinition shaperAssembly = AssemblyDefinition.ReadAssembly(
            shaperAssemblyPath,
            new ReaderParameters { ReadSymbols = false, InMemory = true }
        );
        MethodDefinition shaper = shaperAssembly.MainModule.Types
            .Single(item => item.FullName == "VNRevival.TextShaper")
            .Methods.Single(item => item.Name == "SetText" && item.Parameters.Count == 2);
        MethodReference importedShaper = assembly.MainModule.ImportReference(shaper);
        int changed = 0;
        foreach (TypeDefinition type in WalkTypes(assembly.MainModule.Types))
        {
            foreach (MethodDefinition method in type.Methods.Where(item => item.HasBody))
            {
                foreach (Instruction instruction in method.Body.Instructions)
                {
                    MethodReference called = instruction.Operand as MethodReference;
                    if (instruction.OpCode != OpCodes.Callvirt
                        || called == null
                        || called.Name != "set_text"
                        || called.DeclaringType.FullName != "TMPro.TMP_Text")
                        continue;
                    instruction.OpCode = OpCodes.Call;
                    instruction.Operand = importedShaper;
                    changed++;
                }
            }
        }
        if (changed != 28)
            throw new InvalidDataException(
                String.Format(
                    CultureInfo.InvariantCulture,
                    "Expected 28 TMP_Text.set_text assignments for the pinned build; found {0}",
                    changed
                )
            );
        return changed;
    }

    public static int Main(string[] args)
    {
        if (args.Length != 5 && args.Length != 6)
        {
            Console.Error.WriteLine(
                "usage: PatchManagedStrings INPUT.dll OUTPUT.dll PATCHES.tsv SPEAKER_LABELS.tsv SAVE_LOCATION_LABELS.tsv [TEXT_SHAPER.dll]"
            );
            return 2;
        }

        var patches = new List<Patch>();
        foreach (string line in File.ReadAllLines(args[2], Encoding.UTF8))
        {
            if (String.IsNullOrWhiteSpace(line))
                continue;
            string[] fields = line.Split('\t');
            if (fields.Length != 5)
                throw new InvalidDataException("Malformed patch line");
            patches.Add(new Patch {
                TypeName = fields[0],
                MethodName = fields[1],
                Offset = Int32.Parse(fields[2], NumberStyles.HexNumber, CultureInfo.InvariantCulture),
                Source = Decode(fields[3]),
                Translation = Decode(fields[4]),
            });
        }

        List<DisplayLabel> labels = ReadDisplayLabels(args[3], "speaker display-label");
        List<DisplayLabel> saveLocationLabels = ReadDisplayLabels(args[4], "save-location display-label");

        AssemblyDefinition assembly = AssemblyDefinition.ReadAssembly(
            args[0],
            new ReaderParameters { ReadSymbols = false, InMemory = true }
        );
        TypeDefinition helperType = AddDisplayLabelsType(assembly.MainModule);
        MethodDefinition translateSpeaker = AddDisplayLabelMethod(
            assembly.MainModule,
            helperType,
            "TranslateSpeaker",
            "runtimeKey",
            labels
        );
        if (labels.Count > 0)
            RedirectSpeakerDisplay(assembly, translateSpeaker);
        MethodDefinition translateSaveLocation = AddDisplayLabelMethod(
            assembly.MainModule,
            helperType,
            "TranslateSaveLocation",
            "displayName",
            saveLocationLabels
        );
        if (saveLocationLabels.Count > 0)
            RedirectSaveLocationDisplay(assembly, translateSaveLocation);
        foreach (TypeDefinition type in WalkTypes(assembly.MainModule.Types))
        {
            foreach (MethodDefinition method in type.Methods.Where(item => item.HasBody))
            {
                foreach (Instruction instruction in method.Body.Instructions)
                {
                    if (instruction.OpCode != OpCodes.Ldstr)
                        continue;
                    foreach (Patch patch in patches.Where(item => !item.Applied))
                    {
                        bool typeMatches = type.Name == patch.TypeName || type.FullName == patch.TypeName;
                        if (!typeMatches || method.Name != patch.MethodName || instruction.Offset != patch.Offset)
                            continue;
                        string current = instruction.Operand as string;
                        if (current != patch.Source)
                            throw new InvalidDataException(
                                String.Format(
                                    CultureInfo.InvariantCulture,
                                    "Source mismatch for {0}::{1}@IL_{2:x4}",
                                    patch.TypeName,
                                    patch.MethodName,
                                    patch.Offset
                                )
                            );
                        instruction.Operand = patch.Translation;
                        patch.Applied = true;
                    }
                }
            }
        }

        Patch missing = patches.FirstOrDefault(item => !item.Applied);
        if (missing != null)
        {
            Console.Error.WriteLine(
                String.Format(
                    CultureInfo.InvariantCulture,
                    "Patch target not found: {0}::{1}@IL_{2:x4}",
                    missing.TypeName,
                    missing.MethodName,
                    missing.Offset
                )
            );
            return 1;
        }

        int textShaperRedirects = args.Length == 6
            ? RedirectAllTextAssignments(assembly, args[5])
            : 0;

        assembly.Write(args[1]);
        AssemblyDefinition verification = AssemblyDefinition.ReadAssembly(
            args[1],
            new ReaderParameters { ReadSymbols = false, InMemory = true }
        );
        int verified = 0;
        foreach (TypeDefinition type in WalkTypes(verification.MainModule.Types))
        {
            foreach (MethodDefinition method in type.Methods.Where(item => item.HasBody))
            {
                foreach (Instruction instruction in method.Body.Instructions)
                {
                    if (instruction.OpCode != OpCodes.Ldstr)
                        continue;
                    foreach (Patch patch in patches)
                    {
                        bool typeMatches = type.Name == patch.TypeName || type.FullName == patch.TypeName;
                        if (typeMatches && method.Name == patch.MethodName && instruction.Offset == patch.Offset
                            && (instruction.Operand as string) == patch.Translation)
                            verified++;
                    }
                }
            }
        }
        if (verified != patches.Count)
        {
            Console.Error.WriteLine(
                String.Format(
                    CultureInfo.InvariantCulture,
                    "Post-write verification found {0} of {1} patched strings",
                    verified,
                    patches.Count
                )
            );
            return 1;
        }
        if (labels.Count > 0 || saveLocationLabels.Count > 0)
        {
            TypeDefinition helper = verification.MainModule.Types.Single(
                item => item.FullName == "VNRevival.DisplayLabels"
            );
            MethodDefinition verifiedTranslateSpeaker = helper.Methods.Single(
                item => item.Name == "TranslateSpeaker"
            );
            foreach (DisplayLabel label in labels)
            {
                bool hasRuntimeKey = verifiedTranslateSpeaker.Body.Instructions.Any(
                    item => item.OpCode == OpCodes.Ldstr && (item.Operand as string) == label.RuntimeKey
                );
                bool hasTranslation = verifiedTranslateSpeaker.Body.Instructions.Any(
                    item => item.OpCode == OpCodes.Ldstr && (item.Operand as string) == label.Translation
                );
                if (!hasRuntimeKey || !hasTranslation)
                    throw new InvalidDataException("Speaker display-label verification failed");
            }
            MethodDefinition dialogMethod = WalkTypes(verification.MainModule.Types)
                .Single(item => item.Name == "DialogView")
                .Methods.Single(item => item.Name == "OnDialogReadyToUpdate" && item.HasBody);
            bool hasRedirect = dialogMethod.Body.Instructions.Any(item => {
                MethodReference called = item.Operand as MethodReference;
                return item.OpCode == OpCodes.Call
                    && called != null
                    && called.FullName == verifiedTranslateSpeaker.FullName;
            });
            if (!hasRedirect)
                throw new InvalidDataException("Speaker display redirect verification failed");

            MethodDefinition verifiedTranslateSaveLocation = helper.Methods.Single(
                item => item.Name == "TranslateSaveLocation"
            );
            foreach (DisplayLabel label in saveLocationLabels)
            {
                bool hasRuntimeKey = verifiedTranslateSaveLocation.Body.Instructions.Any(
                    item => item.OpCode == OpCodes.Ldstr && (item.Operand as string) == label.RuntimeKey
                );
                bool hasTranslation = verifiedTranslateSaveLocation.Body.Instructions.Any(
                    item => item.OpCode == OpCodes.Ldstr && (item.Operand as string) == label.Translation
                );
                if (!hasRuntimeKey || !hasTranslation)
                    throw new InvalidDataException("Save-location display-label verification failed");
            }
            MethodDefinition saveLocationMethod = WalkTypes(verification.MainModule.Types)
                .Single(item => item.Name == "SaveFileView")
                .Methods.Single(item => item.Name == "UpdateInfoText" && item.HasBody);
            int saveLocationRedirects = saveLocationMethod.Body.Instructions.Count(item => {
                MethodReference called = item.Operand as MethodReference;
                return item.OpCode == OpCodes.Call
                    && called != null
                    && called.FullName == verifiedTranslateSaveLocation.FullName;
            });
            if (saveLocationRedirects != 2)
                throw new InvalidDataException("Save-location display redirect verification failed");
        }
        if (args.Length == 6)
        {
            int verifiedShaperRedirects = WalkTypes(verification.MainModule.Types)
                .SelectMany(item => item.Methods)
                .Where(item => item.HasBody)
                .SelectMany(item => item.Body.Instructions)
                .Count(item => {
                    MethodReference called = item.Operand as MethodReference;
                    return item.OpCode == OpCodes.Call
                        && called != null
                        && called.DeclaringType.FullName == "VNRevival.TextShaper"
                        && called.Name == "SetText";
                });
            if (verifiedShaperRedirects != textShaperRedirects)
                throw new InvalidDataException("Text-shaper redirect verification failed");
            int remainingDirectAssignments = WalkTypes(verification.MainModule.Types)
                .SelectMany(item => item.Methods)
                .Where(item => item.HasBody)
                .SelectMany(item => item.Body.Instructions)
                .Count(item => {
                    MethodReference called = item.Operand as MethodReference;
                    return item.OpCode == OpCodes.Callvirt
                        && called != null
                        && called.DeclaringType.FullName == "TMPro.TMP_Text"
                        && called.Name == "set_text";
                });
            if (remainingDirectAssignments != 0)
                throw new InvalidDataException("Direct TMP_Text.set_text assignments remain after shaping redirect");
        }
        Console.WriteLine(
            String.Format(
                CultureInfo.InvariantCulture,
                "{0} strings; {1} speaker labels; {2} save-location labels; {3} text-shaper redirects",
                patches.Count,
                labels.Count,
                saveLocationLabels.Count,
                textShaperRedirects
            )
        );
        return 0;
    }
}
