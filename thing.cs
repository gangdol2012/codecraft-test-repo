using System.IO;
using System;
public static class Prog
{
    public static void Main(string[] args)
    {
        Console.Write("How many ouputs? >>> ");
        int value = 0;
        try
        {
            value = int.Parse(Console.ReadLine());
        }
        catch(FormatException)
        {
            Console.Write("Input is invalid.");
        }
        StreamWriter writer = new StreamWriter("log.txt", true);
        for(int i = 1; i <= value; i++)
        {
            string modifier = "th";
            modifier = (i - i / 10 * 10) switch
            {
                1 => "st",
                2 => "nd",
                3 => "rd",
                _ => modifier
            };
            modifier = (i / 10 - i / 100 * 10) switch
            {
                1 => "th",
                _ => modifier
            };
            Console.WriteLine($"TEST: {i}{modifier} output in my IDE.");
            writer.WriteLine($"TEST: {i}{modifier} output in my IDE.");
        }
        writer.Close();
    }
}