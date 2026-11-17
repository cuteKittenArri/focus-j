# 42 Exam Rank 04: Exercises, Solutions & Explanations

This covers every exercise in `level1/` and `level2/`. Each solution below was compiled with
`gcc -Wall -Wextra -Werror` and tested against the subject examples plus extra edge cases
(error paths, fd leaks, zombies, AddressSanitizer for the parsers).

Some solutions differ from the `.c` files in this folder, because a few of those files have bugs.
See [Notes on the files in this folder](#notes-on-the-files-in-this-folder).

## Contents

| Level | Exercise | Topic |
|---|---|---|
| 1 | [ft_popen](#1-ft_popen) | `pipe` + `fork` + `dup2` + `execvp` |
| 1 | [picoshell](#2-picoshell) | a pipeline of N commands (`cmd1 \| cmd2 \| ...`) |
| 1 | [sandbox](#3-sandbox) | signals, `alarm` timeout, exit status decoding |
| 2 | [argo](#4-argo) | recursive descent JSON parser |
| 2 | [vbc](#5-vbc) | recursive descent math expression parser (`+`, `*`, `()`) |

---

# Level 1: processes, pipes, signals

## Background: the syscalls you need

| Call | What it does | Watch out for |
|---|---|---|
| `pipe(fd)` | Creates a one-way channel. Write into `fd[1]`, read from `fd[0]`. | A reader only gets EOF (`read` returns 0) once **every** copy of `fd[1]` is closed, in **every** process. |
| `fork()` | Duplicates the process. Returns `0` in the child, the child's pid in the parent, `-1` on error. | The child gets a copy of **all** open fds. |
| `dup2(old, new)` | Makes `new` point to the same file as `old` (closing `new` first). | After `dup2`, close `old`, because you now have two fds pointing at the same pipe end. |
| `execvp(file, argv)` | Replaces the current process with the program `file` (searched in `PATH`). | Only returns if it **failed**, so always follow it with `exit(1)`. |
| `wait` / `waitpid` | Reaps a finished child and gives its exit status. | A child that is never reaped stays a zombie. |

> **Golden rule:** after every `fork`, each process closes every pipe end it does not use.
> Forgetting this causes the two classic bugs: **hangs** (the reader never sees EOF because a
> forgotten write end is still open) and **fd leaks**.

---

## 1. ft_popen

### Subject

```
Assignment name  : ft_popen
Expected files   : ft_popen.c
Allowed functions: pipe, fork, dup2, execvp, close, exit
```

Write `int ft_popen(const char *file, char *const argv[], char type);`

- Run `file` with `argv` (using `execvp`).
- `type == 'r'`: return an fd connected to the **output** of the command (you read what it prints).
- `type == 'w'`: return an fd connected to the **input** of the command (you write what it reads).
- On error or invalid parameter, return `-1`. Don't leak fds.

### Solution

```c
#include <unistd.h>
#include <stdlib.h>

int	ft_popen(const char *file, char *const argv[], char type)
{
	int	fd[2];
	int	pid;

	if (!file || !argv || (type != 'r' && type != 'w'))
		return (-1);
	if (pipe(fd) == -1)
		return (-1);
	pid = fork();
	if (pid == -1)
	{
		close(fd[0]);
		close(fd[1]);
		return (-1);
	}
	if (pid == 0)
	{
		if (type == 'r' && dup2(fd[1], STDOUT_FILENO) == -1)
			exit(1);
		if (type == 'w' && dup2(fd[0], STDIN_FILENO) == -1)
			exit(1);
		close(fd[0]);
		close(fd[1]);
		execvp(file, argv);
		exit(1);
	}
	if (type == 'r')
	{
		close(fd[1]);
		return (fd[0]);
	}
	close(fd[0]);
	return (fd[1]);
}
```

### Explanation

```
type 'r':   [child: cmd] stdout = fd[1] ====pipe====> fd[0]  -> returned, parent READS
type 'w':   parent WRITES  <- returned  fd[1] ====pipe====> fd[0] = stdin [child: cmd]
```

1. **Validate input.** A NULL `file` or `argv`, or a `type` other than `'r'`/`'w'`, returns `-1`
   before anything is opened, so nothing can leak.
2. **`pipe(fd)`** creates the channel.
3. **`fork()`.** If it fails, close **both** pipe ends before returning `-1` (otherwise they leak).
4. **Child:**
   - `'r'`: the parent wants to read what the command prints, so the command's **stdout** must
     become the pipe's write end: `dup2(fd[1], STDOUT_FILENO)`.
   - `'w'`: the parent wants to feed the command, so the command's **stdin** must become the pipe's
     read end: `dup2(fd[0], STDIN_FILENO)`.
   - Close both original pipe fds. The one we need now lives on as 0 or 1; the other is unused.
   - `execvp`. If it returns, it failed (e.g. the command doesn't exist), so `exit(1)`.
5. **Parent:** keep the end you use, close the other, return the one you kept.

**Why the parent must close the other end:** with `'r'`, if the parent kept `fd[1]` open, a
writer would still exist. `read()` on `fd[0]` would then never return 0 (EOF), so a
`get_next_line` loop would block forever. It's also an fd leak.

**Things to know:**
- A nonexistent command still returns a valid fd. The error happens in the child **after** the
  fork: the child exits with 1 and the reader just gets EOF immediately. That's normal (real
  `popen` behaves the same way).
- `ft_popen` doesn't `wait`. Like the real `popen`/`pclose`, waiting is the caller's job.

---

## 2. picoshell

### Subject

```
Assignment name:	picoshell
Expected files:		picoshell.c
Allowed functions:	close, fork, wait, exit, execvp, dup2, pipe
```

Write `int picoshell(char **cmds[]);`

- `cmds` is a NULL-terminated list of commands. Each `cmds[i]` is an `argv` array ready for `execvp`.
- Run them as a pipeline: the output of each command goes into the input of the next.
- On any error, return `1` (after closing all fds). Otherwise wait for all children and return `0`.

```
./picoshell echo 'squalala' "|" cat "|" sed 's/a/b/g'
squblblb
```

### The idea

N commands need N-1 pipes. Loop over the commands and remember `prev`, the **read end of the
previous pipe**, which becomes the stdin of the current command.

```
         pipe A                 pipe B
cmd0 ──> [A1 ═══ A0] ──> cmd1 ──> [B1 ═══ B0] ──> cmd2
(stdin =                                          (stdout =
 terminal)                                         terminal)

iteration 0: make pipe A, cmd0: stdout=A1.               parent: close A1, prev=A0
iteration 1: make pipe B, cmd1: stdin=A0, stdout=B1.     parent: close A0, B1, prev=B0
iteration 2: no pipe,     cmd2: stdin=B0.                parent: close B0
```

The parent never holds more than **one** fd (`prev`) between iterations, so there are no leaks
even with 1000 commands.

### Solution

```c
#include <unistd.h>
#include <stdlib.h>
#include <sys/wait.h>

int	picoshell(char **cmds[])
{
	int	fd[2];
	int	prev = -1;
	int	pid;
	int	status;
	int	ret = 0;
	int	i = 0;

	while (cmds[i])
	{
		if (cmds[i + 1] && pipe(fd) == -1)
		{
			ret = 1;
			break ;
		}
		pid = fork();
		if (pid == -1)
		{
			if (cmds[i + 1])
			{
				close(fd[0]);
				close(fd[1]);
			}
			ret = 1;
			break ;
		}
		if (pid == 0)
		{
			if (prev != -1)
			{
				if (dup2(prev, STDIN_FILENO) == -1)
					exit(1);
				close(prev);
			}
			if (cmds[i + 1])
			{
				close(fd[0]);
				if (dup2(fd[1], STDOUT_FILENO) == -1)
					exit(1);
				close(fd[1]);
			}
			execvp(cmds[i][0], cmds[i]);
			exit(1);
		}
		if (prev != -1)
			close(prev);
		prev = -1;
		if (cmds[i + 1])
		{
			close(fd[1]);
			prev = fd[0];
		}
		i++;
	}
	if (prev != -1)
		close(prev);
	while (wait(&status) > 0)
		if (!WIFEXITED(status) || WEXITSTATUS(status) != 0)
			ret = 1;
	return (ret);
}
```

### Explanation

**Each iteration:**

1. `if (cmds[i + 1] && pipe(fd) == -1)`: only create a pipe if there **is** a next command.
   The last command writes to the real stdout.
2. `fork()`.
3. **Child:**
   - If there is a previous pipe: `dup2(prev, STDIN_FILENO)`, then close `prev`.
   - If there is a next command: close `fd[0]` (this child never reads its own output), then
     `dup2(fd[1], STDOUT_FILENO)`, then close `fd[1]`.
   - `execvp`. If it returns, `exit(1)`.
4. **Parent:**
   - Close `prev`. The child has its own copy now; the parent doesn't need it anymore.
   - Close `fd[1]`. **This is critical.** If the parent kept a write end open, the next command
     (e.g. `cat`) would never get EOF and the pipeline would hang forever.
   - Keep `fd[0]` as `prev` for the next command.

**Error handling:** on a `pipe` or `fork` failure we don't `return` right away, we `break`. That
way the code after the loop still closes `prev` **and waits for the children that were already
started** (no zombies, no leaked fds), and then returns `1`.

**Return value:** `while (wait(&status) > 0)` reaps every child (`wait` returns `-1` once none
are left). If any child didn't exit normally with code 0, return `1`. The subject says
"if any error occur, return 1", and the provided `main.c` expects a nonexistent command to make
`picoshell` return non-zero. (Some people just `return 0` after waiting. That's also seen as
accepted, but it fails the "Invalid command" test of the provided `main.c`.)

**Why `wait` and not `waitpid`?** Only `wait` is in the allowed functions list.

---

## 3. sandbox

### Subject

```
Assignment name  : sandbox
Expected files   : sandbox.c
Allowed functions: fork, waitpid, exit, alarm, sigaction, kill, printf, strsignal,
                   errno, sigaddset, sigemptyset, sigfillset, sigdelset, sigismember
```

Write `int sandbox(void (*f)(void), unsigned int timeout, bool verbose);`

- Return `1` if `f` is nice, `0` if it's bad, `-1` on an internal error.
- **Bad** means: killed or stopped by a signal (segfault, abort...), exited with a code other
  than 0, or timed out.
- If `verbose`, print one of these:
  ```
  Nice function!
  Bad function: exited with code <exit_code>
  Bad function: <signal description>
  Bad function: timed out after <timeout> seconds
  ```
- Don't leak processes (not even zombies).

### The idea

Run `f` in a **child process**, so if it crashes or loops forever, only the child dies. The
parent waits for it, with a timeout built from `alarm()`:

1. Install a SIGALRM handler that does **nothing**, **without** `SA_RESTART`.
2. `alarm(timeout)`: after `timeout` seconds the kernel sends SIGALRM to the parent.
3. The parent is blocked in `waitpid`. When SIGALRM arrives, the handler runs, and because
   `SA_RESTART` is not set, `waitpid` is **interrupted**: it returns `-1` with `errno == EINTR`.
4. That means it timed out: `kill(pid, SIGKILL)`, then `waitpid` again to reap the dead child
   (otherwise it would stay a zombie).

**Why install a handler at all?** The default action of SIGALRM is to **terminate the process**.
Without a handler, the alarm would kill the sandbox (the parent) itself.

### Solution

```c
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <signal.h>
#include <unistd.h>
#include <sys/wait.h>

static void	alarm_handler(int sig)
{
	(void)sig;
}

int	sandbox(void (*f)(void), unsigned int timeout, bool verbose)
{
	struct sigaction	sa;
	pid_t				pid;
	int					status;

	sa.sa_handler = alarm_handler;
	sa.sa_flags = 0;
	sigemptyset(&sa.sa_mask);
	if (sigaction(SIGALRM, &sa, NULL) == -1)
		return (-1);
	pid = fork();
	if (pid == -1)
		return (-1);
	if (pid == 0)
	{
		f();
		exit(0);
	}
	alarm(timeout);
	if (waitpid(pid, &status, 0) == -1)
	{
		if (errno != EINTR)
			return (-1);
		kill(pid, SIGKILL);
		waitpid(pid, NULL, 0);
		if (verbose)
			printf("Bad function: timed out after %u seconds\n", timeout);
		return (0);
	}
	alarm(0);
	if (WIFEXITED(status))
	{
		if (WEXITSTATUS(status) == 0)
		{
			if (verbose)
				printf("Nice function!\n");
			return (1);
		}
		if (verbose)
			printf("Bad function: exited with code %d\n", WEXITSTATUS(status));
		return (0);
	}
	if (WIFSIGNALED(status))
	{
		if (verbose)
			printf("Bad function: %s\n", strsignal(WTERMSIG(status)));
		return (0);
	}
	return (-1);
}
```

### Explanation

**Decoding `status`:**

| Macro | Meaning |
|---|---|
| `WIFEXITED(status)` | Child ended normally (`exit()` or returned from main) |
| `WEXITSTATUS(status)` | ...with this exit code |
| `WIFSIGNALED(status)` | Child was killed by a signal |
| `WTERMSIG(status)` | ...this signal. `strsignal()` turns it into text, e.g. `"Segmentation fault"` |

**Line by line:**

- `sa.sa_flags = 0` means **no** `SA_RESTART`. This is what makes `waitpid` return `EINTR`
  instead of silently restarting after the alarm.
- Child: `f(); exit(0);`. If `f` returns normally, the child exits with 0, so the function is
  "nice". Without that `exit(0)`, the child would return from `sandbox` and keep running the
  caller's code, giving two copies of the program.
- `alarm(0)` after a normal `waitpid` **cancels** the pending alarm. Otherwise the SIGALRM would
  arrive later and interrupt some unrelated syscall in the caller.
- `kill(pid, SIGKILL)`: SIGKILL can't be caught or ignored, so even a function that ignores
  SIGALRM/SIGTERM and loops forever dies. The second `waitpid` reaps it, so no zombie.

**Things to know:**

- `strsignal` text depends on the OS: Linux prints `Segmentation fault` / `Aborted`, macOS
  prints `Segmentation fault: 11` / `Abort trap: 6`. The exam runs on Linux.
- A function that **stops** itself (`raise(SIGSTOP)`) is not reported by `waitpid` (that would
  need `WUNTRACED`), so it gets killed by the timeout and reported as timed out. It is still
  correctly reported as bad (returns 0) and leaves no zombie.
- If you test with `./a.out | cat` you may see some lines printed **twice**. `printf` output is
  buffered when stdout isn't a terminal, the child inherits the unflushed buffer, and `exit()`
  in the child flushes it again. Run tests in a terminal to avoid that (`fflush` isn't in the
  allowed list).

---

# Level 2: recursive descent parsers

Both level 2 exercises use the same technique: a **recursive descent parser**. You write the
grammar, then write **one function per grammar rule**. Each function looks at the next character
to decide what to do, and calls the other rule functions (or itself) for the nested parts.

The given code provides the same helper trio in both exercises:

| Helper | Does |
|---|---|
| `peek` / `**s` | Look at the next char without consuming it |
| `accept(c)` | If the next char is `c`, consume it and return 1, else return 0 (no error) |
| `expect(c)` | Like `accept`, but prints the "unexpected" error if it doesn't match |
| `unexpected` | Prints `Unexpected token 'X'` or `Unexpected end of input` |

---

## 4. argo

### Subject

```
Assignment name: argo
Expected files: argo.c
Allowed functions: getc, ungetc, printf, malloc, calloc, realloc, free, isdigit, fscanf, write
```

Write `int argo(json *dst, FILE *stream);`, which parses JSON from `stream` into the `json`
AST (given struct). Return `1` on success, `-1` on failure.

- Only handle **numbers** (ints like `scanf("%d")`), **strings** and **maps** (objects).
- Strings: escapes only for `\\` and `\"`.
- **No spaces.** A space is an invalid token.
- On error print `unexpected token '%c'` or `unexpected end of input`.
- The given `main` re-serializes the AST, so the output must equal the input.

```
$> echo -n '{"tomatoes":42,"potatoes":234}' | ./argo /dev/stdin | cat -e
{"tomatoes":42,"potatoes":234}$
$> echo -n '"unfinished string' | ./argo /dev/stdin | cat -e
unexpected end of input$
$> echo -n '{"no value?":}' | ./argo /dev/stdin | cat -e
unexpected token '}'$
```

### Grammar

```
value  := map | string | int
map    := '{' '}'
        | '{' string ':' value ( ',' string ':' value )* '}'
string := '"' ( any char except '"' and '\'  |  '\' any char )* '"'
int    := what scanf("%d") reads (optional '-', digits)
```

### Solution

Keep **everything** from the given file (the `json`/`pair` structs, `peek`, `unexpected`,
`accept`, `expect`, `free_json`, `serialize`, `main`) and add this below it:

```c
int	parse_value(json *dst, FILE *stream);

int	parse_int(json *dst, FILE *stream)
{
	int	n;

	if (fscanf(stream, "%d", &n) != 1)
	{
		unexpected(stream);
		return (-1);
	}
	dst->type = INTEGER;
	dst->integer = n;
	return (1);
}

char	*parse_str(FILE *stream)
{
	char	*str;
	char	*tmp;
	size_t	len;
	int		c;

	if (!expect(stream, '"'))
		return (NULL);
	str = calloc(1, 1);
	len = 0;
	while (str)
	{
		c = getc(stream);
		if (c == '"')
			return (str);
		if (c == '\\')
			c = getc(stream);
		if (c == EOF)
		{
			unexpected(stream);
			break ;
		}
		tmp = realloc(str, len + 2);
		if (!tmp)
			break ;
		str = tmp;
		str[len++] = c;
		str[len] = '\0';
	}
	free(str);
	return (NULL);
}

int	parse_map(json *dst, FILE *stream)
{
	pair	*tmp;
	pair	*cur;

	dst->type = MAP;
	dst->map.size = 0;
	dst->map.data = NULL;
	if (!expect(stream, '{'))
		return (-1);
	if (accept(stream, '}'))
		return (1);
	while (1)
	{
		tmp = realloc(dst->map.data, (dst->map.size + 1) * sizeof(pair));
		if (!tmp)
			return (-1);
		dst->map.data = tmp;
		cur = &dst->map.data[dst->map.size++];
		cur->key = NULL;
		cur->value.type = INTEGER;
		cur->key = parse_str(stream);
		if (!cur->key)
			return (-1);
		if (!expect(stream, ':'))
			return (-1);
		if (parse_value(&cur->value, stream) == -1)
			return (-1);
		if (accept(stream, '}'))
			return (1);
		if (!expect(stream, ','))
			return (-1);
	}
}

int	parse_value(json *dst, FILE *stream)
{
	int		c;
	char	*str;

	c = peek(stream);
	if (c == '{')
		return (parse_map(dst, stream));
	if (c == '"')
	{
		str = parse_str(stream);
		if (!str)
			return (-1);
		dst->type = STRING;
		dst->string = str;
		return (1);
	}
	if (isdigit(c) || c == '-')
		return (parse_int(dst, stream));
	unexpected(stream);
	return (-1);
}

int	argo(json *dst, FILE *stream)
{
	dst->type = INTEGER;
	if (parse_value(dst, stream) == -1)
		return (-1);
	if (peek(stream) != EOF)
	{
		unexpected(stream);
		return (-1);
	}
	return (1);
}
```

### Explanation

**`parse_value`** is the dispatcher. It peeks at the first char: `{` means a map, `"` means a
string, a digit or `-` means an int. Anything else (including a space or EOF) is an error.

**`parse_int`**: `fscanf("%d")` is allowed and does all the work, including negative numbers.
It returns 1 if it read a number.

**`parse_str`:**
- `expect('"')` consumes the opening quote, or prints the error (e.g. for a key like `{1:2}`).
- `int c`, **not** `char c`. `getc` returns an `int` so that `EOF` (-1) can be told apart from
  every real byte. With a `char`, the `c == EOF` check breaks: it never matches where `char` is
  unsigned (ARM Linux), so you loop forever. Where `char` is signed, byte `0xFF` is mistaken for EOF.
- A backslash means "take the next char literally": `\"` becomes `"`, `\\` becomes `\`.
  `serialize` adds the backslash back when printing, so output == input.
- The string grows with `realloc`, so there is no fixed-size buffer that could overflow.
- On EOF, `unexpected(stream)` sees the stream is at EOF and prints `unexpected end of input`.
  That covers both `"unfinished string` and `"unfinished string 2\"` (the `\"` is an escaped
  quote, not the closing one). The partial string is freed.

**`parse_map`:**
- `accept('}')` right after `{` handles the empty map `{}`. It must **consume** the `}`.
- Loop: `key` `:` `value`, then either `}` (done) or `,` (next pair). Anything else gives an
  error from `expect(',')`, e.g. `{"a":1 "b":2}` gives `unexpected token ' '`.
- A trailing comma `{"a":1,}` fails naturally: after the `,` we expect a key string, and
  `parse_str`'s `expect('"')` reports `unexpected token '}'`.

**Memory safety on errors.** This is the subtle part. On failure, the given `main` calls
`free_json(file)` on whatever `argo` produced, so the tree must **always be in a freeable state**,
even half-built:
- `argo` sets `dst->type = INTEGER` first. If the very first char is invalid, `free_json` sees an
  INTEGER and frees nothing (instead of reading garbage from an uninitialized struct).
- In `parse_map`, a new pair slot is set to `key = NULL`, `value.type = INTEGER` **before**
  anything is parsed into it. If parsing fails halfway, `free_json` frees what exists, and
  `free(NULL)` is harmless.
- `argo` itself never frees on error. `main` does that, and freeing in both places would be a
  double free.

**Trailing input check.** After a complete value, `argo` checks that nothing is left
(`peek != EOF`). That rejects `1x`, `{"a":1}}`, or a trailing newline. That's why the subject
always uses `echo -n`: a plain `echo` adds `\n`, which is an invalid token.

**Error message casing:** the subject text says `Unexpected token`, but the examples and the
given `unexpected()` print lowercase `unexpected token`. Use the given function unchanged.

**Tested results:**

| Input | Output |
|---|---|
| `1` / `-42` | `1` / `-42` |
| `"escape! \" "` | `"escape! \" "` |
| `{}` / `{"a":{},"b":1}` | `{}` / `{"a":{},"b":1}` |
| `{"recursion":{"recursion":"recursion"}}` | same as input |
| `"unfinished string` | `unexpected end of input` |
| `{"no value?":}` | `unexpected token '}'` |
| `{"a":1,}` | `unexpected token '}'` |
| `{"a":1` | `unexpected end of input` |
| `{1:2}` | `unexpected token '1'` |
| `{"a" :1}` | `unexpected token ' '` |
| `1x` | `unexpected token 'x'` |

---

## 5. vbc

### Subject

```
Assignment name  : vbc
Expected files   : *.c *.h
Allowed functions: malloc, calloc, realloc, free, printf, isdigit, write
```

Write a program that prints the result of a math expression given as an argument.

- Operators `+`, `*`, and parentheses. Values are single digits `0`-`9`. No whitespace.
- On an unexpected symbol: print `Unexpected token '%c'` and exit with 1.
  If the symbol is the end of input: `Unexpected end of input`.
- On a syscall failure: exit with 1.

```
$> ./vbc '3+4*5'           -> 23
$> ./vbc '(3+4)*5'         -> 35
$> ./vbc '1+'              -> Unexpected end of input
$> ./vbc '1+2)'            -> Unexpected token ')'
$> ./vbc '((1+3)*12+(3*(2+6))'  -> Unexpected token '2'
```

### Grammar (this is the key to the exercise)

```
sum     := product ( '+' product )*
product := factor  ( '*' factor  )*
factor  := DIGIT | '(' sum ')'
```

**Operator precedence comes from the call depth.** `sum` calls `product`, which calls `factor`.
The deeper a rule is, the tighter it binds. `*` lives one level deeper than `+`, so in `3+4*5`
the `product` rule grabs `4*5` as one unit before `sum` ever sees the `+`.
Parentheses restart at the top (`sum`) from inside the deepest rule (`factor`), which is why
they override precedence.

```
'3+4*5'                    '(3+4)*5'
      ADD                       MULTI
     /   \                     /     \
    3   MULTI               ADD       5
        /   \              /   \
       4     5            3     4
   = 3 + 20 = 23            = 7 * 5 = 35
```

### Solution

Start from the given file. Changes: remove the placeholder line `node *n(**s);` (it doesn't
compile), change `<malloc.h>` to `<stdlib.h>`, fill in the parser, and add `return (0);` at the
end of `eval_tree` (otherwise gcc's `-Werror` fails with "control reaches end of non-void function").

```c
#include <stdio.h>
#include <stdlib.h>
#include <ctype.h>

typedef struct node {
    enum {
        ADD,
        MULTI,
        VAL
    }   type;
    int val;
    struct node *l;
    struct node *r;
}   node;

node    *parse_sum(char **s);

node    *new_node(node n)
{
    node *ret = calloc(1, sizeof(n));
    if (!ret)
        return (NULL);
    *ret = n;
    return (ret);
}

void    destroy_tree(node *n)
{
    if (!n)
        return ;
    if (n->type != VAL)
    {
        destroy_tree(n->l);
        destroy_tree(n->r);
    }
    free(n);
}

void    unexpected(char c)
{
    if (c)
        printf("Unexpected token '%c'\n", c);
    else
        printf("Unexpected end of input\n");
}

int accept(char **s, char c)
{
    if (**s == c)
    {
        (*s)++;
        return (1);
    }
    return (0);
}

int expect(char **s, char c)
{
    if (accept(s, c))
        return (1);
    unexpected(**s);
    return (0);
}

node    *join(int type, node *l, node *r)
{
    node    *ret;

    if (!r)
    {
        destroy_tree(l);
        return (NULL);
    }
    ret = new_node((node){.type = type, .l = l, .r = r});
    if (!ret)
    {
        destroy_tree(l);
        destroy_tree(r);
    }
    return (ret);
}

node    *parse_factor(char **s)
{
    node    *ret;

    if (isdigit(**s))
    {
        ret = new_node((node){.type = VAL, .val = **s - '0'});
        (*s)++;
        return (ret);
    }
    if (accept(s, '('))
    {
        ret = parse_sum(s);
        if (ret && !expect(s, ')'))
        {
            destroy_tree(ret);
            return (NULL);
        }
        return (ret);
    }
    unexpected(**s);
    return (NULL);
}

node    *parse_product(char **s)
{
    node    *left;

    left = parse_factor(s);
    while (left && accept(s, '*'))
        left = join(MULTI, left, parse_factor(s));
    return (left);
}

node    *parse_sum(char **s)
{
    node    *left;

    left = parse_product(s);
    while (left && accept(s, '+'))
        left = join(ADD, left, parse_product(s));
    return (left);
}

node    *parse_expr(char *s)
{
    node    *ret;

    ret = parse_sum(&s);
    if (ret && *s)
    {
        unexpected(*s);
        destroy_tree(ret);
        return (NULL);
    }
    return (ret);
}

int eval_tree(node *tree)
{
    switch (tree->type)
    {
        case ADD:
            return (eval_tree(tree->l) + eval_tree(tree->r));
        case MULTI:
            return (eval_tree(tree->l) * eval_tree(tree->r));
        case VAL:
            return (tree->val);
    }
    return (0);
}

int main(int argc, char **argv)
{
    if (argc != 2)
        return (1);
    node *tree = parse_expr(argv[1]);
    if (!tree)
        return (1);
    printf("%d\n", eval_tree(tree));
    destroy_tree(tree);
}
```

### Explanation

**`parse_factor`:** the smallest unit.
- A digit becomes a `VAL` leaf; consume it.
- `(` means consume it, parse a whole `sum` inside, then `expect(')')`.
- Anything else (`+`, `*`, `)`, a letter, or `\0`) is an error. `unexpected('\0')` prints
  `Unexpected end of input`.

**`parse_product` / `parse_sum`:** same shape. Parse the left operand, then while the next char is
the operator, parse another operand and combine both into a new node. Building `left = op(left, right)`
in a loop makes the operators **left-associative**: `1+2+3` becomes `(1+2)+3`.

**`join(type, l, r)`** combines two subtrees, and takes care of all the cleanup:
- If `r` is NULL (the right side failed to parse), free `l` and return NULL.
- If `malloc` fails, free both and return NULL (a syscall failure, so `main` exits with 1).

That lets the loops be one line: as soon as anything fails, `left` becomes NULL, the
`while (left && ...)` stops, and the NULL propagates all the way up with no leaks.

**`parse_expr`:** after parsing a full `sum`, there must be nothing left. If there is
(e.g. `1+2)`), that leftover char is the unexpected token. This replaces any separate
"check parentheses balance" pass: a stray `)` is caught here, and a missing `)` is caught by
`expect(')')` in `parse_factor`.

**Where each error is detected:**

| Input | Output | Detected by |
|---|---|---|
| `1+` | `Unexpected end of input` | `parse_factor` sees `\0` after `+` |
| `1+2)` | `Unexpected token ')'` | `parse_expr`: leftover `)` |
| `((1+2)*3` | `Unexpected end of input` | `expect(')')` sees `\0` |
| `1++2` | `Unexpected token '+'` | `parse_factor` sees `+` |
| `(*1+2)` | `Unexpected token '*'` | `parse_factor` sees `*` |
| `12` | `Unexpected token '2'` | `parse_expr`: leftover `2` (numbers are single digits) |
| `((1+3)*12+(3*(2+6))` | `Unexpected token '2'` | `expect(')')` after `(1+3)*1` sees `2` |
| `''` (empty) | `Unexpected end of input` | `parse_factor` sees `\0` |
| `abc` | `Unexpected token 'a'` | `parse_factor` sees `a` |

**Overflow:** `9*9*9*9*9*9*9*9*9*9` overflows `int`. The reference uses `int` too, so the
(wrapped-around) output matches. Don't "fix" it.

---

## Notes on the files in this folder

These problems were found while testing the existing `.c` files (macOS, `gcc -Wall -Wextra -Werror`):

| File | Problem |
|---|---|
| `level1/ft_popen/ft_popen.c` | ✅ Correct. |
| `level1/picoshell/picoshell.c` | Always returns `0`, so it **fails** the "Invalid command" test of the provided `main.c`. If `pipe`/`fork` fails mid-pipeline, it leaks `last_fd` and returns without waiting for the children already started. |
| `level1/sandbox/sandbox.c` | Works. Minor: doesn't cancel the alarm (`alarm(0)`) when `f` finishes in time, and ignores a `sigaction` failure. |
| `level2/argo/argo.c` | `{}` doesn't consume its `}`, so `{"a":{},"b":1}` prints `{"a":{}}` (wrong). Negative ints are rejected (`-42` gives `unexpected token '-'`). Uses `char c` with `getc`/EOF. Fixed 4096-byte buffer (overflow on long strings), leaked on error. On an error at the first char, `main` calls `free_json` on an uninitialized struct (possible crash). |
| `level2/vbc/vbc.c` | Prints `Unexpected end of **file**` instead of `input`. Doesn't really validate syntax: `''` prints `0`, `1++2` prints `3`, `1**2` prints `0`, `(*1+2)` prints `2`, `1+2)(` prints `3`. |
| `level2/vbc/vbc0.c` | For a stray `)` (`1+2)`) it prints `Unexpected token ')'` **without** `\n`. It ignores leftover input (`1(2)` prints `1`). |

> ⚠️ `level2/vbc/tester.sh` uses `vbc.c` as its **reference**, so the correct vbc solution above
> is marked FAIL on 9 of its tests (`''`, `1+`, `1++2`, `1**2`, `1+2*`, `(*1+2)`, `1+2)(`,
> `((1+2)*3`, `(((((2+2)*2+2)*2+2)*2+2)*2`). In every one of those, the solution above is the one that matches the subject.
>
> The level 1 testers count open fds through `/proc/self/fd`, which only exists on Linux.
> On macOS that check silently passes no matter what.

---

## Exam cheat sheet

**ft_popen**: validate, then `pipe`, then `fork` (close both on fail). Child: `dup2` the right end
(`'r'`: `fd[1]`→1, `'w'`: `fd[0]`→0), close both, `execvp`, `exit(1)`. Parent: close the other end,
return yours.

**picoshell**: `prev = -1`. Loop: pipe if there's a next command, then fork. Child: `prev`→0,
`fd[1]`→1, close all, exec. Parent: close `prev`, close `fd[1]`, `prev = fd[0]`. On error `break`.
After the loop: close `prev`, `while (wait(&st) > 0)`, return 1 if any child failed.

**sandbox**: empty SIGALRM handler, `sa_flags = 0`, then fork (child: `f(); exit(0);`), then
`alarm(t)`, then `waitpid`. On `EINTR`: `kill(SIGKILL)` + `waitpid` = timeout. Otherwise `alarm(0)`,
then `WIFEXITED`/`WEXITSTATUS`/`WIFSIGNALED`/`strsignal(WTERMSIG)`.

**argo**: `value → map | string | int`. `int c` for `getc`. Keep the tree freeable at all times
(set `type` before parsing, init each new pair). Check for trailing input at the end.

**vbc**: `sum → product ('+' product)*`, `product → factor ('*' factor)*`,
`factor → digit | '(' sum ')'`. Check for leftover input at the end. Free subtrees on every error path.
