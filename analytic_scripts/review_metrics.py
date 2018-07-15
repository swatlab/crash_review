import json, csv, os, re, string
from datetime import datetime
import numpy
from base64 import b64decode
import pandas as pd

# Compute date interval between two date strings
def dateDiff(d1_str, d2_str):
    d1 = datetime.strptime(d1_str, '%Y%m%d%H%M%S')
    d2 = datetime.strptime(d2_str, '%Y%m%d%H%M%S')
    return (d2 - d1).total_seconds()/3600

# Load crash inducing commits
def loadCrashInducingCommits(filepath):
    crash_inducing_commits = set()
    with open(filepath, 'r') as f:
        csvreader = csv.reader(f)
        next(csvreader, None)
        for row in csvreader:
            crash_inducing_commits |= set(row[1].split('^'))
    return crash_inducing_commits

# A patch's related comments
def relatedComments(bug_id, attach_id):
    total_times, total_words = 0, 0
    commenter_set = set()
    with open('../bugs/comment/{}.json'.format(bug_id)) as f:
        for comment_item in json.load(f)['bugs'][bug_id]['comments']:
                commenter_set.add(comment_item['author'])
                raw_comment = comment_item['text']
                matched = re.findall(r'Review of attachment ([0-9]+)', raw_comment)
                if len(matched):
                    if attach_id == int(matched[0]):
                        comment_times, comment_words = 0, 0
                        for line in raw_comment.split('\n')[2:]:
                            if not ((line.startswith('>') or line.startswith('Review of attachment') or line.startswith('(In reply to'))):
                                if re.search(r'[a-zA-Z]', line):
                                    comment_words += len(re.findall(r'\S+', line.encode('utf-8').translate(None, string.punctuation)))
                                    comment_times += 1
                        total_times += comment_times
                        total_words += comment_words
    return total_times, total_words, commenter_set

# Extract C/CPP files from attachment data
def extractFilesFromAttachment(patch_text):
    changed_files = set()
    for line in patch_text.split('\n'):
        files = re.findall(r'^diff\s+\-\-git\s+\S+\s+(\S+)', line)
        if len(files):
            if re.search(r'(c|cpp|cc|cxx|h|hpp|hxx)$', files[0]):
                changed_files.add(re.sub(r'^b\/', '', files[0]))    # remove the prefix "b/"
    return '^'.join(changed_files)

def mean(num_list):
    if set(num_list) == set([-1]):
        return -1
    else:
        return numpy.mean([0 if n==-1 else n for n in num_list]) 

def reviewerOrigin(reviewer_email_set):
    mozilla, external = False, False
    for an_email in reviewer_email_set:
        if an_email.endswith('mozilla.com'):
            mozilla = True
        else:
            external = True
    if mozilla and external:
        return 'both'
    elif mozilla ==  True and external == False:
        return 'mozilla'
    return 'external'

# A bug's review metrics
def reviewMetrics(bug_id):
    attach_file = '../bugs/attachment/{}.json'.format(bug_id)
    if os.path.exists(attach_file):
        total_patches, approved_patches, obsolete_cnt = 0, 0, 0
        iteration_list, ct_list, cw_list, reviewer_cnt_list, reviewer_comm_list = list(), list(), list(), list(), list()
        n_author_list, neg_review_list, review_delay_list, review_dur_list, patch_size_list = list(), list(), list(), list(), list()
        fb_cnt_list, neg_fb_list, fb_delay_list = list(), list(), list()
        reviewer_email_set = set()
        with open(attach_file) as f:
            for attach_item in json.load(f)['bugs'][bug_id]:
                if attach_item['is_patch']:
                    if (attach_item['content_type'] == 'text/plain') and (isinstance(attach_item['data'], unicode)):
                        patch_text = b64decode(attach_item['data']).strip()
                        patched_cpp_files = extractFilesFromAttachment(patch_text)
                        if len(patched_cpp_files):
                            attach_id = attach_item['id']
                            attach_flags = attach_item['flags']
                            attach_author = attach_item['creator']
                            attach_date = re.sub(r'[^0-9]', '', attach_item['creation_time'])
                            is_obsolete = attach_item['is_obsolete']
                            # analyze patches (including the obsolete ones)
                            if len(attach_flags):
                                print '  attach:', attach_id
                                # count total reviewed or review requested patches
                                total_patches += 1
                                # count obsolete patches in a bug
                                if is_obsolete == 1:
                                    obsolete_cnt += 1
                                review_iterations = 0
                                feedback_cnt, neg_feedbacks = 0, 0
                                reviewer_set = set()
                                first_review_date, last_review_date, first_feedback_date = None, None, None
                                pos_votes, neg_votes = 0, 0
                                for a_flag in attach_flags:
                                    if 'review' in a_flag['name']:
                                        if first_review_date == None:
                                            first_review_date = re.sub(r'[^0-9]', '', a_flag['modification_date'])
                                        last_review_date = re.sub(r'[^0-9]', '', a_flag['modification_date'])
                                        if a_flag['setter'] != attach_author:
                                            reviewer_set.add(a_flag['setter'])
                                            reviewer_email_set.add(a_flag['setter'])
                                        if a_flag['status'] == '+':
                                            pos_votes += 1
                                        elif a_flag['status'] == '-':
                                            neg_votes += 1
                                        review_iterations += 1
                                    elif 'feedback' in a_flag['name']:
                                        if first_feedback_date == None:
                                            first_feedback_date = re.sub(r'[^0-9]', '', a_flag['modification_date'])
                                        if a_flag['status'] == '-':
                                            neg_feedbacks += 1
                                        feedback_cnt += 1
                                iteration_list.append(review_iterations)
                                fb_cnt_list.append(feedback_cnt)
                                reviewer_cnt_list.append(len(reviewer_set))
                                # proportion of negative reviews
                                if pos_votes + neg_votes:
                                    neg_review_rate =  neg_votes/(pos_votes+neg_votes)
                                else:
                                    neg_review_rate = -1
                                neg_review_list.append(neg_review_rate)
                                # number of negative feedbacks
                                neg_fb_list.append(neg_feedbacks)
                                # non author voters
#                                non_author_voters = len(reviewer_set - set([attach_author]))
#                                n_author_list.append(non_author_voters)
                                # review delay and review duration
                                if first_review_date:
                                    response_delay = dateDiff(attach_date, first_review_date)
                                    review_duration = dateDiff(attach_date, last_review_date)
                                else:
                                    response_delay = -1
                                    review_duration = -1
                                review_delay_list.append(response_delay)
                                review_dur_list.append(review_duration)
                                # feedback delay
                                if first_feedback_date:
                                    feedback_delay = dateDiff(attach_date, first_feedback_date)
                                else:
                                    feedback_delay = -1
                                fb_delay_list.append(feedback_delay)
                                # comment metrics
                                total_comment_times, total_comment_words, commenter_set = relatedComments(bug_id, attach_id)
                                if len(reviewer_set):
                                    reviewer_comment_rate = len(reviewer_set & commenter_set) / len(reviewer_set)
                                else:
                                    reviewer_comment_rate = 0
                                reviewer_comm_list.append(reviewer_comment_rate)
                                ct_list.append(total_comment_times)
                                cw_list.append(total_comment_words)
                                # whether the patched has been approved
                                if attach_flags[-1]['status'] == '+':
                                    approved_patches += 1 
                                # patch size
                                patch_size_list.append(len(patch_text.split('\n')))
            if total_patches:
                obsolete_patch_rate = obsolete_cnt/total_patches
                if approved_patches/total_patches == 1:
                    reviewed = '+'
                else:
                    reviewed = '?'
            else:
                return 'no review'
            reviewer_origin = 'none'
            if reviewed == '+':
                reviewer_origin = '^'.join(reviewer_email_set)
        return [bug_id, mean(iteration_list), mean(ct_list), mean(cw_list), mean(reviewer_cnt_list), mean(reviewer_comm_list), 
                mean(neg_review_list), mean(review_delay_list), mean(review_dur_list), mean(patch_size_list),
                mean(fb_cnt_list), max(neg_fb_list), mean(fb_delay_list), obsolete_patch_rate, reviewer_origin, reviewed]
    return None

if __name__ == '__main__':
    DEBUG = False
    output_list = list()
    # load crash-inducing commits
    crash_inducing_commits = loadCrashInducingCommits('../new_data/crash_inducing_commits.csv')
    # iterativly extract each bug's review metrics
    i = 0
    with open('../new_data/bug_commit_mapping.json') as f:
        bug2commit = json.load(f)
        for bug_id in bug2commit:
            if DEBUG and i > 500:
                break
            print bug_id            
            review_metrics = reviewMetrics(bug_id)
            if review_metrics:
                '''# whether crash-inducing
                crash_inducing = False
                related_commits = bug2commit[bug_id]
                for commit_id in related_commits:                
                    if commit_id in crash_inducing_commits:
                        crash_inducing = True
                        break
                # review metrics'''
                reviewed = None
                if review_metrics == 'no review':
                    pass
                else:
                    '''output_list.append(review_metrics + [crash_inducing])'''
                    output_list.append(review_metrics)
                i += 1            
    # output results
    df = pd.DataFrame(output_list, columns=['bug_id', 'review_iterations', 'comment_times', 'comment_words', 'reviewers', 'reviewer_comment_rate', 
                                            'neg_review_rate', 'response_delay', 'review_duration', 'patch_size',
                                            'feedback_count', 'neg_feedback', 'feedback_delay', 'obsolete_rate', 'reviewer_origin', 'reviewed'])
    df_output = df.round(decimals=2).fillna(-1)
    if DEBUG:
        print df_output
    else:
        df_output.to_csv('../new_statistics/review_metrics2.csv', index=False)
    
    