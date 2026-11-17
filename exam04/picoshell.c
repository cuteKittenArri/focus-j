#include <stdlib.h>
#include <sys/wait.h>
#include <unistd.h>

int picoshell(char **cmds[])
{
	int fd[2];
	int prev = -1;
	int status;
	int ret = 0;
	int i = 0;
	int pid;

	while (cmds[i])
	{
		if (cmds[i + 1] && pipe(fd) == -1)
		{
			ret = 1;
			break;
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
			break;
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
	{
		if (WIFEXITED(status) && WEXITSTATUS(status) != 0)
			ret = 1;
	}
	return (ret);
}
