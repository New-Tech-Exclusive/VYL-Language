#Simple Python script, used to show the benchmark

import time

print("Starting benchmark: counting to 1,000,000,000...")

start = time.process_time()
i = 0
while i < 1000000000:
    i += 1
end = time.process_time()

elapsed = end - start
print(f"Time taken (seconds): \n{elapsed:.6f}")
print("Finished.")
