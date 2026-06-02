using System;

foreach (var thing in typeof(string).GetMethods())
{
    Console.WriteLine(thing.ToString());
}
