import sys, csv, re, json, subprocess
import pandas as pd

# Execute a shell command
def shellCommand(command_str):
    cmd = subprocess.Popen(command_str, shell=True, stdout=subprocess.PIPE)
    cmd_out, cmd_err = cmd.communicate()
    return cmd_out

# Load bug crashed date
def loadCrashedDate(filename):
    crashed_date_dict = dict()
    with open(filename, 'r') as f:
        csvreader = csv.reader(f)
        for line in csvreader:
            crashed_date_dict[line[0]] = line[1]
    return crashed_date_dict

# Load commit date
def loadCommitDate():
    df = pd.read_csv('../new_data/commit_date.csv')
    return df.set_index('commit_id')['commit_date'].to_dict()

# Extract deleted line numbers for a commit
def changedLines(commit_id, file_path):
    deleted_delta_cnt = 0
    deleted_line_set = set()
    # request diff from the Hg repository
    diff_res = shellCommand('hg -R %s diff -c %s %s' %(HG_REPO_PATH,commit_id,file_path))
    # extract changed lines
    for line in diff_res.split('\n'):
        if re.search(r'@@[\+\-\,0-9\s]+@@', line):
            changed_range = re.findall(r'@@(.+)@@', line)[0].strip()
            deleted_range = changed_range.split(' ')[0][1:].split(',')
            deleted_delta_cnt = 0
        else:
            if re.search(r'^\-\s', line):
                deleted_line_set.add(int(deleted_range[0]) + deleted_delta_cnt)
                deleted_delta_cnt += 1
            else:
                deleted_delta_cnt += 1
    return deleted_line_set
    
#   Detect changed revision numbers for each bug fix
def filterCandidate(annotate_res, deleted_line_set):
    candidate_set = set()
    block_comment = False
    for line in annotate_res.split('\n'):
        if len(line):
            elems = line.split(':', 2)
            commit = elems[0].strip()
            line_num = elems[1].strip()
            changed_code = elems[2].strip()
            #   filter out the meaningless lines (i.e., lines without letters), and comment lines
            if len(changed_code) > 0 and re.search(r'[a-zA-Z]', changed_code):                
                if block_comment:
                    if '*/' in changed_code:
                        block_comment = False
                        valid_code = re.sub(r'.+\*\/', '', changed_code)
                elif ('/*' in changed_code) and ('*/' not in changed_code):
                    block_comment = True
                    valid_code = re.sub(r'\/\*.+', '', changed_code)
                else:
                    valid_code = re.sub(r'\/\*.+\*\/', '', re.sub(r'\/\/.+', '', changed_code))
                #   take only the valid lines as bug-inducing candidates
                if len(valid_code) > 0 and re.search(r'[a-zA-Z]', valid_code):
                    #print rev_num, '\t', changed_code
                    if int(line_num) in deleted_line_set:
                        candidate_set.add(commit)
    return candidate_set    

# Perform Hg annotate command
def hgAnnotate(commit_id, file_list):
    candidate_set = dict()
    for f in file_list:
        if re.search(r'(\.c|\.cpp|\.cc|\.cxx|\.h|\.hpp|\.hxx)$', f):
            file_path = HG_REPO_PATH + f
            deleted_line_set = changedLines(commit_id, file_path)
            # blame the parent revision, and select the "-" lines' corresponding revision numbers
            parent_commit = commit_id + '^'
            blame_res = shellCommand('hg -R %s annotate -r %s %s -c -l -w -b -B' %(HG_REPO_PATH,parent_commit,file_path))  
            #crash_inducing_candidates |= filterCandidate(cmd_out, deleted_line_set)
            candidate_set = filterCandidate(blame_res, deleted_line_set)
    return candidate_set

# Identify crash-inducing commit for each crash-related bug
def crashInducing(crashed_date, bug_fix_commits, commit_date_dict):
    crash_inducing_commits = set()
    for commit_id in bug_fix_commits:
        # extract a commit's modified and deleted files, and its parent sha
        cmd_out = shellCommand('hg -R %s log -r %s --template "{file_mods}\n{file_dels}"' %(HG_REPO_PATH,commit_id))
        items = cmd_out.split('\n')
        changed_files = set(items[0].split(' ') + items[1].split(' '))
        # apply SZZ algorithm
        candidate_set = hgAnnotate(commit_id, changed_files)
        # candidate must be committed before the bug's crashed date
        if len(candidate_set):
            if DEBUG:
                print '\t', candidate_set
            for candidate_commit in candidate_set:
                candidate_date = str(commit_date_dict[candidate_commit])
                if DEBUG:
                    print candidate_date, crashed_date
                if candidate_date < crashed_date:
                    crash_inducing_commits.add(candidate_commit)
                    if DEBUG:
                        print '\t', candidate_commit
    return crash_inducing_commits

# Iteratively identify each bug's buggy commits
def identification(json_file, crashed_date_dict, commit_date_dict):
    result_list = list()   
    with open(json_file, 'r') as f:
        mapping_dict = json.load(f)
        i = 0
        for bug_id in mapping_dict:    
            if bug_id in crashed_date_dict and int(bug_id) >= 537438:
                if DEBUG:
                    i += 1
                    if i > 20:
                        break
                print bug_id
                crashed_date = crashed_date_dict[bug_id]
                bug_fix_commits = mapping_dict[bug_id]
                crash_inducing_commits = crashInducing(crashed_date, bug_fix_commits, commit_date_dict)
                # add crash_inducing commits to the result list
                if len(crash_inducing_commits):
                    result_list.append([bug_id, '^'.join(crash_inducing_commits)])
                    # flush memory             
                    shellCommand('sudo sysctl -w vm.drop_caches=3')
    return result_list

def outputResults(result_list, outputfile):
    df = pd.DataFrame(result_list, columns=['crash_related_bug', 'crash_inducing_commits'])
    df.to_csv(outputfile, index=False)
    return

if __name__ == '__main__':
    # Initialisation
    DEBUG = False
    HG_REPO_PATH = '../../mozilla_clone/firefox/'
    # Analytic functions
    crashed_date_dict = loadCrashedDate('../new_data/crashed_date.csv')
    commit_date_dict = loadCommitDate()
    result_list = identification('../new_data/cpp_related_bugs.json', crashed_date_dict, commit_date_dict)
    # output results
    outputResults(result_list, '../new_data/crash_inducing_commits.csv')
    
