# Commands to Run — Debug adapter 500 error

## Test the adapter import inside the container

```bash
sudo docker run --rm --entrypoint /bin/bash azuregovcloud-test:1.0.0 -c "cd /home/aria-ops-adapter-user/src/app && python3 -c 'from adapter import get_adapter_definition; print(str(True))'"
```

## If that fails, try a simpler test first

```bash
sudo docker run --rm --entrypoint /bin/bash azuregovcloud-test:1.0.0 -c "cd /home/aria-ops-adapter-user/src/app && python3 -c 'import adapter; print(str(True))'"
```

## If import adapter fails, check for syntax errors

```bash
sudo docker run --rm --entrypoint /bin/bash azuregovcloud-test:1.0.0 -c "cd /home/aria-ops-adapter-user/src/app && python3 -c 'import py_compile; py_compile.compile(str(\"adapter.py\"), doraise=True)'"
```

## Paste all output into ErrorFile.txt
