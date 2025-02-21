using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;

// Regular function
public static int Add(int a, int b)
{
    return a + b;
}

// Generic method
public static T Maximum<T>(T a, T b) where T : IComparable<T>
{
    return a.CompareTo(b) > 0 ? a : b;
}

// Lambda expression
Func<int, int, int> multiply = (x, y) => x * y;

// Interface
public interface ICalculator
{
    int Calculate(int x, int y);
}

// Class with properties and methods
public class Calculator : ICalculator
{
    // Auto-implemented property
    public int Value { get; set; }

    // Constructor
    public Calculator(int initialValue = 0)
    {
        Value = initialValue;
    }

    // Method implementation
    public int Calculate(int x, int y)
    {
        return x + y;
    }

    // Expression-bodied method
    public int Subtract(int a, int b) => a - b;

    // Static method
    public static double Divide(double a, double b) => a / b;

    // Async method
    public async Task<int> CalculateAsync(int x)
    {
        await Task.Delay(100);
        return x * 2;
    }

    // Generic method with constraints
    public T Power<T>(T baseNum, int exp) where T : struct
    {
        dynamic result = baseNum;
        for (int i = 1; i < exp; i++)
        {
            result *= baseNum;
        }
        return result;
    }

    // Protected virtual method
    protected virtual void Update() { }
}

// Derived class with override
public class AdvancedCalculator : Calculator
{
    // Property with backing field
    private int _precision;
    public int Precision
    {
        get => _precision;
        set => _precision = value > 0 ? value : 1;
    }

    // Override method
    protected override void Update()
    {
        Console.WriteLine($"Updated with precision {Precision}");
    }
}

// Extension method
public static class Extensions
{
    public static int Square(this int number)
    {
        return number * number;
    }
}

// Record type (C# 9.0+)
public record Point(int X, int Y);

// Namespace with nested types
namespace MathOperations
{
    public static class Advanced
    {
        public static double Cube(double x) => x * x * x;
    }
}

// Pattern matching
public static class PatternExample
{
    public static string Classify(object obj) => obj switch
    {
        int i when i < 0 => "Negative",
        int i => "Positive",
        string s => "Text",
        _ => "Unknown"
    };
}

// Tuple return type
public static (int sum, int product) Calculate(int a, int b)
{
    return (a + b, a * b);
}

// Nullable reference type
public class Optional
{
    public string? NullableString { get; set; }
}

// Main method (entry point)
public class Program
{
    public static async Task Main()
    {
        var calc = new Calculator();
        var result = await calc.CalculateAsync(5);
        Console.WriteLine(result);
    }
} 