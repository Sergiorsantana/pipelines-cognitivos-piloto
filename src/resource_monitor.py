# -*- coding: utf-8 -*-
"""Mede CPU (%) e memória (MB) reais do processo durante a execução de uma
função, usando amostragem em thread separada via psutil."""
import threading
import time

import psutil

_NCPU = psutil.cpu_count() or 1
_CPU_CEIL = 100.0 * _NCPU  # teto fisicamente possivel de %CPU do processo


def run_with_monitoring(func, *args, poll_interval=0.01, **kwargs):
    proc = psutil.Process()
    samples_cpu = []
    samples_mem = []
    stop_flag = {"stop": False}
    result_holder = {}

    def sampler():
        proc.cpu_percent(interval=None)  # "descarta" a primeira leitura (referência)
        last_t = time.perf_counter()
        while not stop_flag["stop"]:
            time.sleep(poll_interval)
            now = time.perf_counter()
            dt = now - last_t
            reading = proc.cpu_percent(interval=None)
            last_t = now
            # so aceita a leitura se o intervalo real entre chamadas foi
            # suficiente para o psutil calcular a percentagem com confianca
            # (intervalos quase-nulos geram picos espurios por divisao por ~0)
            if dt >= 0.008 and 0.0 <= reading <= _CPU_CEIL:
                samples_cpu.append(reading)
            samples_mem.append(proc.memory_info().rss / (1024 * 1024))

    def worker():
        result_holder["result"] = func(*args, **kwargs)

    t_sampler = threading.Thread(target=sampler)
    t_worker = threading.Thread(target=worker)

    t_sampler.start()
    t_worker.start()
    t_worker.join()
    stop_flag["stop"] = True
    t_sampler.join()

    cpu_avg = sum(samples_cpu) / len(samples_cpu) if samples_cpu else 0.0
    mem_peak = max(samples_mem) if samples_mem else proc.memory_info().rss / (1024 * 1024)

    metrics = result_holder["result"]
    metrics["cpu_avg_pct"] = cpu_avg
    metrics["mem_peak_mb"] = mem_peak
    return metrics
