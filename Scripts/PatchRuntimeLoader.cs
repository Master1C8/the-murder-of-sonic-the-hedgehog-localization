using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using Mono.Cecil;
using Mono.Cecil.Cil;

internal static class PatchRuntimeLoader
{
    private static IEnumerable<TypeDefinition> WalkTypes(IEnumerable<TypeDefinition> roots)
    {
        foreach (TypeDefinition type in roots)
        {
            yield return type;
            foreach (TypeDefinition nested in WalkTypes(type.NestedTypes))
                yield return nested;
        }
    }

    private static MethodDefinition RuntimeMethod(
        AssemblyDefinition runtime,
        string name,
        int parameterCount
    )
    {
        return runtime.MainModule.Types
            .Single(item => item.FullName == "VNRevival.Runtime")
            .Methods.Single(item => item.Name == name && item.Parameters.Count == parameterCount);
    }

    private static int PatchInitialize(AssemblyDefinition assembly, MethodReference initialize)
    {
        MethodDefinition awake = assembly.MainModule.Types
            .Single(item => item.FullName == "GameManager")
            .Methods.Single(item => item.Name == "Awake" && item.HasBody);
        List<Instruction> returns = awake.Body.Instructions
            .Where(item => item.OpCode == OpCodes.Ret)
            .ToList();
        if (returns.Count != 1)
            throw new InvalidDataException("Unexpected GameManager.Awake return layout");
        awake.Body.GetILProcessor().InsertBefore(returns[0], Instruction.Create(OpCodes.Call, initialize));
        return 1;
    }

    private static int PatchStoryLoader(AssemblyDefinition assembly, MethodReference loadStory)
    {
        MethodDefinition startStory = assembly.MainModule.Types
            .Single(item => item.FullName == "StoryManager")
            .Methods.Single(item => item.Name == "StartStory" && item.HasBody);
        List<Instruction> textReads = startStory.Body.Instructions.Where(item => {
            MethodReference called = item.Operand as MethodReference;
            return (item.OpCode == OpCodes.Call || item.OpCode == OpCodes.Callvirt)
                && called != null
                && called.DeclaringType.FullName == "UnityEngine.TextAsset"
                && called.Name == "get_text";
        }).ToList();
        if (textReads.Count != 1)
            throw new InvalidDataException("Expected one StoryManager TextAsset read");
        startStory.Body.GetILProcessor().InsertAfter(
            textReads[0],
            Instruction.Create(OpCodes.Call, loadStory)
        );
        return 1;
    }

    private static int RedirectAllTextAssignments(
        AssemblyDefinition assembly,
        MethodReference setText
    )
    {
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
                    instruction.Operand = setText;
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

    private static int PatchTextAnimationCompletion(
        AssemblyDefinition assembly,
        MethodReference shouldComplete
    )
    {
        TypeDefinition animator = assembly.MainModule.Types.Single(
            item => item.FullName == "AnimateTMProVertex"
        );
        TypeDefinition iterator = animator.NestedTypes.Single(
            item => item.Name == "<AnimateVertices>d__16"
        );
        MethodDefinition moveNext = iterator.Methods.Single(
            item => item.Name == "MoveNext" && item.HasBody
        );
        if (moveNext.Body.Variables.Count < 5
            || moveNext.Body.Variables[1].VariableType.FullName != animator.FullName
            || moveNext.Body.Variables[4].VariableType.MetadataType != MetadataType.Int32)
            throw new InvalidDataException("Unexpected AnimateVertices local-variable layout");

        VariableDefinition animatorLocal = moveNext.Body.Variables[1];
        VariableDefinition characterCountLocal = moveNext.Body.Variables[4];
        FieldDefinition animating = animator.Fields.Single(item => item.Name == "animating");
        FieldDefinition skipCalled = animator.Fields.Single(item => item.Name == "skipCalled");
        FieldDefinition letterDelay = animator.Fields.Single(item => item.Name == "letterDelay");
        FieldDefinition duration = animator.Fields.Single(item => item.Name == "duration");
        FieldDefinition animStart = iterator.Fields.Single(item => item.Name == "<animStartTime>5__4");
        MethodDefinition onAnimationComplete = animator.Methods.Single(
            item => item.Name == "OnAnimationComplete" && item.Parameters.Count == 0
        );
        MethodReference getTime = moveNext.Body.Instructions
            .Select(item => item.Operand as MethodReference)
            .First(item => item != null
                && item.DeclaringType.FullName == "UnityEngine.Time"
                && item.Name == "get_time");
        List<Instruction> waits = moveNext.Body.Instructions.Where(item => {
            MethodReference called = item.Operand as MethodReference;
            return item.OpCode == OpCodes.Newobj
                && called != null
                && called.DeclaringType.FullName == "UnityEngine.WaitForEndOfFrame";
        }).ToList();
        if (waits.Count != 2)
            throw new InvalidDataException("Unexpected AnimateVertices frame-yield layout");
        Instruction waitForNextFrame = waits[1];
        ILProcessor il = moveNext.Body.GetILProcessor();
        Action<Instruction> insert = instruction => il.InsertBefore(waitForNextFrame, instruction);

        insert(il.Create(OpCodes.Ldloc, animatorLocal));
        insert(il.Create(OpCodes.Ldfld, animating));
        insert(il.Create(OpCodes.Brfalse, waitForNextFrame));
        insert(il.Create(OpCodes.Call, getTime));
        insert(il.Create(OpCodes.Ldarg_0));
        insert(il.Create(OpCodes.Ldfld, animStart));
        insert(il.Create(OpCodes.Ldloc, characterCountLocal));
        insert(il.Create(OpCodes.Ldloc, animatorLocal));
        insert(il.Create(OpCodes.Ldfld, letterDelay));
        insert(il.Create(OpCodes.Ldloc, animatorLocal));
        insert(il.Create(OpCodes.Ldfld, duration));
        insert(il.Create(OpCodes.Ldloc, animatorLocal));
        insert(il.Create(OpCodes.Ldfld, skipCalled));
        insert(il.Create(OpCodes.Call, shouldComplete));
        insert(il.Create(OpCodes.Brfalse, waitForNextFrame));
        insert(il.Create(OpCodes.Ldloc, animatorLocal));
        insert(il.Create(OpCodes.Ldc_I4_0));
        insert(il.Create(OpCodes.Stfld, animating));
        insert(il.Create(OpCodes.Ldloc, animatorLocal));
        insert(il.Create(OpCodes.Ldc_I4_0));
        insert(il.Create(OpCodes.Stfld, skipCalled));
        insert(il.Create(OpCodes.Ldloc, animatorLocal));
        insert(il.Create(OpCodes.Callvirt, onAnimationComplete));
        return 1;
    }

    private static int CountCalls(AssemblyDefinition assembly, string typeName, string methodName)
    {
        return WalkTypes(assembly.MainModule.Types)
            .SelectMany(item => item.Methods)
            .Where(item => item.HasBody)
            .SelectMany(item => item.Body.Instructions)
            .Count(item => {
                MethodReference called = item.Operand as MethodReference;
                return item.OpCode == OpCodes.Call
                    && called != null
                    && called.DeclaringType.FullName == typeName
                    && called.Name == methodName;
            });
    }

    public static int Main(string[] args)
    {
        if (args.Length != 3)
        {
            Console.Error.WriteLine("usage: PatchRuntimeLoader INPUT.dll OUTPUT.dll VNRevival.Runtime.dll");
            return 2;
        }
        AssemblyDefinition runtime = AssemblyDefinition.ReadAssembly(
            args[2],
            new ReaderParameters { ReadSymbols = false, InMemory = true }
        );
        AssemblyDefinition assembly = AssemblyDefinition.ReadAssembly(
            args[0],
            new ReaderParameters { ReadSymbols = false, InMemory = true }
        );
        ModuleDefinition module = assembly.MainModule;
        MethodReference initialize = module.ImportReference(RuntimeMethod(runtime, "Initialize", 0));
        MethodReference loadStory = module.ImportReference(RuntimeMethod(runtime, "LoadStory", 1));
        MethodReference setText = module.ImportReference(RuntimeMethod(runtime, "SetText", 2));
        MethodReference shouldComplete = module.ImportReference(
            RuntimeMethod(runtime, "ShouldCompleteTextAnimation", 6)
        );

        int initializeHooks = PatchInitialize(assembly, initialize);
        int storyHooks = PatchStoryLoader(assembly, loadStory);
        int textRedirects = RedirectAllTextAssignments(assembly, setText);
        int animationGuards = PatchTextAnimationCompletion(assembly, shouldComplete);
        assembly.Write(args[1]);

        AssemblyDefinition verification = AssemblyDefinition.ReadAssembly(
            args[1],
            new ReaderParameters { ReadSymbols = false, InMemory = true }
        );
        if (CountCalls(verification, "VNRevival.Runtime", "Initialize") != initializeHooks
            || CountCalls(verification, "VNRevival.Runtime", "LoadStory") != storyHooks
            || CountCalls(verification, "VNRevival.Runtime", "SetText") != textRedirects
            || CountCalls(verification, "VNRevival.Runtime", "ShouldCompleteTextAnimation") != animationGuards)
            throw new InvalidDataException("Runtime-loader post-write verification failed");
        int remaining = WalkTypes(verification.MainModule.Types)
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
        if (remaining != 0)
            throw new InvalidDataException("Direct TMP_Text.set_text assignments remain");

        Console.WriteLine(
            String.Format(
                CultureInfo.InvariantCulture,
                "{0} initializer; {1} story loader; {2} text redirects; {3} animation guard",
                initializeHooks,
                storyHooks,
                textRedirects,
                animationGuards
            )
        );
        return 0;
    }
}
