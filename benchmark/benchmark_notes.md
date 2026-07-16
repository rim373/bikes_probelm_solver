**Plus ou moins synchro avec http://192.168.69.164:8102/note/Benchmark%20RP **

## Timeit
### Garbage Collector 
https://docs.python.org/3/library/timeit.html#timeit.Timer.timeit
```py
    # normal
    t = timeit.timeit(lambda: load_and_solve(n), number = x)
    # activate garbage collection:
    t = timeit.timeit(lambda: load_and_solve(n), "gc.enable()", number = x)
```

## Benchmark RP 1
Il doit y avoir une instance à 90 stations qui est tres difficile
il faudrait essayer en activant le garbage collector

## Benchmark RP 2
Apres plusieurs run cf ![](./benchmark_rp_2.1.png) et autres

on observe les memes courbes, avec qqs variations statistiques attribuables au CPU/à l'OS

Apres une inspection detaillée des instances de taille 80:
```
>>> for i in range(10):
...     timeit.timeit(lambda: load_and_solve_param(params[80][i]), number = 1)
...

0.4985606580012245
5.812406373999693
0.05156860400165897
0.11196905500037246
0.18419880799774546
0.11583815899939509
0.20065561500086915
0.06882289400164154
0.045865502001106506
0.0828086359979352
```
Il y en a qui prennent ENORMEMNT de temps et d'autres tres peu: on a gardé ces instances dans les fichiers en `benchmark_rp_2.80.*.dat`.  
Il faudtrait en faire une analyse détaillée.
