import json, csv, re, os, subprocess
from numpy import mean
import pandas as pd

# Execute a shell command
def shellCommand(command_str):
    cmd =subprocess.Popen(command_str.split(' '), stdout=subprocess.PIPE)
    cmd_out, cmd_err = cmd.communicate()
    return cmd_out

def loadReleaseDate():
    rel_date_list = list()
    rel_list = list()
    with open('../new_data/release2commit.csv') as f:
        csvreader = csv.reader(f)
        for row in csvreader:
            rel_num = row[0]
            rel_date = re.sub(r'[^0-9]', '', row[2])
            rel_date_list.append([rel_date, rel_num])
            rel_list.append(rel_num)
    return rel_date_list, list(reversed(rel_list))

def loadCommitDate():
    df = pd.read_csv('../new_data/commit_date.csv')
    return df.set_index('commit_id')['commit_date'].to_dict()

def correspondingRelease(commit_id, commit_date_dict, rel_date_list):
    commit_date = str(commit_date_dict[commit_id])[:-6]
    for item in rel_date_list:
        if commit_date >= item[0]:
            return item[1]
    return rel_date_list[-1][1]

def removePrefix(path):
    return re.sub(r'^[\/\.]+', '', path)

def loadMetrics4Releases(category, release_list):
    rel_metric_dict = dict()
    metric_names = None
    for rel in release_list:
        metric_dict = dict()
        metric_file = '../new_data/code_metrics/%s-%s.csv' %(category, rel.replace('.', '_'))
        with open(metric_file, 'r') as f:
            csvreader = csv.reader(f)
            metric_names = next(csvreader, None)[1:]
            for line in csvreader:
                key = removePrefix(line[0])
                metric_dict[key] = line[1:]
            rel_metric_dict[rel] = metric_dict
    return rel_metric_dict, metric_names

def extractSourceCodeMetrics(rel_date_list, rel_list, commit_date_dict, cpp_changed_dict, category):
    # load metrics
    rel_metric_dict, metric_names = loadMetrics4Releases(category, rel_list)
    # map and compute metric values
    result_list = list()
    i = 0
    with open('../new_data/cpp_related_bugs.json') as f:
        bug2commit = json.load(f)
        for bug_id in bug2commit:
            if DEBUG and i > 30:
                break
            print bug_id
            # extract metrics
            raw_list = list()
            metric_list = list()
            changed_file_list, churn_list = list(), list()
            related_commits = bug2commit[bug_id]
            for commit_id in related_commits:
                if DEBUG:
                    print ' ', commit_id
                # corresponding (prior) release of a commit
                rel_num = correspondingRelease(commit_id, commit_date_dict, rel_date_list)                 
                # changed files and churn in a commit                
                cpp_changed_files = list()
                if category == 'complexity':
                    os.chdir(HG_REPO_PATH)  # change to the HG directory
                    shell_res = shellCommand('hg log -r %s --stat --template {node|short}\n' %commit_id)
                    #print shellCommand('hg diff -c %s' %(commit_id))
                    churn, changed_file_cnt = 0, 0
                    for line in shell_res.split('\n'):
                        matched = re.findall(r'(\S+\.(?:c|cpp|cc|cxx|h|hpp|hxx))\s+\|\s+([0-9]+)\s[\+\-]+$', line)
                        if len(matched):
                            churn += int(matched[0][1])
                            cpp_changed_files.append(matched[0][0])
                    changed_file_list.append(len(cpp_changed_files))
                    churn_list.append(churn)
                    os.chdir(CURRENT_DIR)   # change back to the script directory    
                # map file/node to metrics
                if category == 'complexity':
                    cpp_changed_dict[commit_id] = set()
                else:
                    cpp_changed_files = cpp_changed_dict[commit_id]
                for a_file in cpp_changed_files:
                    metric_dict = rel_metric_dict[rel_num]
                    for node in metric_dict:
                        if node in a_file: 
                            if category == 'complexity':
                                cpp_changed_dict[commit_id].add(node)
                            metrics = metric_dict[node]
                            raw_list.append(metrics)
            # compute average/sum value for a specific attachment
            if category == 'complexity':
                avg_changed_files = mean(changed_file_list)
                avg_churn = mean(churn_list)
                metric_list = [avg_changed_files, avg_churn]
                header_prefix = ['bug_id', 'changed_files', 'churn']
            else:
                header_prefix = ['bug_id']
            if len(raw_list):
                df = pd.DataFrame(raw_list, columns=metric_names).apply(pd.to_numeric)
                for metric_name in metric_names:
                    metric_list.append(df[metric_name].mean())
                result_list.append([bug_id] + metric_list)
            else:
                metric_list += [0]*len(metric_names)
                result_list.append([bug_id] + metric_list)
            i += 1        
    shellCommand('sudo sysctl -w vm.drop_caches=3')
    return pd.DataFrame(result_list, columns=header_prefix+metric_names)

if __name__ == '__main__':
    DEBUG = True
    HG_REPO_PATH = '../../mozilla_clone/firefox/'
    CURRENT_DIR = os.getcwd()
    # load data
    print 'Loading data ...'
    rel_date_list, rel_list = loadReleaseDate()
    commit_date_dict = loadCommitDate()    
    # extract source code metrics
    print 'Extracting code complexity metrics ...'
    cpp_changed_dict = dict()
    df_complexity = extractSourceCodeMetrics(rel_date_list, rel_list, commit_date_dict, cpp_changed_dict, 'complexity')
    print 'Extracting SNA metrics ...'
    df_sna = extractSourceCodeMetrics(rel_date_list, rel_list, commit_date_dict, cpp_changed_dict, 'sna')
    print 'Outputing results ...'
    df_code = pd.merge(df_complexity, df_sna, on='bug_id').round(decimals=2)
    if DEBUG:
        print df_code
    else:
        df_code.to_csv('../new_statistics/basic_metrics.csv', index=False)
        print 'Done.'
    
    
