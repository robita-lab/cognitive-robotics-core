#include "orchestrator.h"

std::mutex mtx_cout; //mutex protecting global variable cout

void printmutex(std::ostream& os, std::string name, std::string msg){
  std::unique_lock<std::mutex> unique_cout(mtx_cout);
  os << "[" << name << "]: "<< msg << std::endl;
}


std::ostream& operator<<(std::ostream &os, const Msg &m) {
  os << "Msg from " << m.src << " to " << m.dst << " with value " << m.value << " and content: " << m.msg;
  return os;
}


std::ostream& operator<<(std::ostream& os, const Params& p) {
  if (p.m == nullptr) {
    os << "Params: k = " << p.k << " m = nullptr";
  } else {
    os << "Params: k = " << p.k << " m = " << *p.m;
  }
  return os;
}
    
std::ostream& operator<<(std::ostream& os, const NeckParams& p) {
  if (p.other == nullptr) {
    os << "NeckParams: other = nullptr";
  } else {
    os << "NeckParams: other = " << p.other;
  }
  return os;
}

//WORKER
void worker::work(Params* p) {
  //std::stringstream ss;
  //ss << *p;
  //ESP_LOGI(pcTaskGetName(nullptr), "[%d]Thworker.work() Params received: %s", wrapth.thid, ss.str().c_str());
  //ESP_LOGD(pcTaskGetName(nullptr), "[%d]Thworker.work() before setup", wrapth.thid);
  
  this->setup(p);
  while (!terminate) {//attribute terminate is controlled by orchestrator
    //printmutex(std::cout, name, "Need to continue working...");
    std::unique_lock<std::mutex> unique_worker(mtx_worker);//std::unique_lock with this constructor also invokes lock
    cond_worker.wait(unique_worker, [this] { return this->worker_turn; });
    if (!terminate) {
      // if (!p->blocking)
      //     p->m = queue.try_pop(); // might return nullptr
      // else
      //ESP_LOGI(pcTaskGetName(nullptr), "[%d]Thworker.work() before pop ", wrapth.thid);  
      p->m = pending_tasks.pop_front();//blocking
      //std::stringstream ss2;
      //ss2 << p->m;
      //ESP_LOGI(pcTaskGetName(nullptr), "[%d]Thworker.work() Msg received: %s", wrapth.thid, ss2.str().c_str());
      //critical section
      this->criticalSection(p);
      //critical section end
      //std::stringstream ss3;
      //ss3 << p->m;
      //ESP_LOGI(pcTaskGetName(nullptr), "[%d]Thworker.work() Msg processed: %s", wrapth.thid, ss3.str().c_str());
    }
    //when working normally or when terminating:
    worker_turn = false;
    // manual unlocking is done before notifying, to avoid waking up
    // the waiting thread only to block again (see notify_one for details)
    unique_worker.unlock();
    cond_worker.notify_one();
  }
  this->wrapUp(p);
  printmutex(std::cout, name, "Work finished");
  
}//std::unique_lock invokes unlock when exiting the scope, in this case the function

//this method can be virtual and subclasses reimplement it accordingly
//once the derived classes have this implemented, remove!
void worker::criticalSection(){
  a++;
}

//NECK
void neck::setup(Params* p) {
  //log
}
  
void neck::criticalSection(Params* p) {
  //receive movement/gesture order and play it when the schedule coordinates
  //for the time being just log it
  //std::stringstream ss;
  //ss << *p;
  //ESP_LOGI(pcTaskGetName(nullptr), "[%d]neck.criticalSection(): %s Params received: " , wrapth.thid, ss.str().c_str());
  
  //NeckParams* incParams = static_cast<NeckParams*>(p);
  //std::stringstream ss2;
  //ss2 << incParams << ":"<< *incParams;
  //ESP_LOGI(pcTaskGetName(nullptr), "[%d]neck.criticalsection() NeckParams %s", wrapth.thid,  ss2.str().c_str());
  
  //critical section
  //++incParams->m->value;
  //critical section end
  //ESP_LOGI(pcTaskGetName(nullptr), "neck.criticalsection() after incrementing");
  //mandar mensaje a la cola del otro thread
  //incParams->m->dst = incParams->other->wrapth.thid;
  //incParams->m->src = wrapth.thid;
  //ESP_LOGI(pcTaskGetName(nullptr), "[%d]neck.criticalsection() before sending msg %d", wrapth.thid, incParams->m->value);
  //incParams->other->wrapth.pushMsg(incParams->m);
  //incParams->keepwork = --incParams->k > 0;
  
  
}

void neck::wrapUp(Params* p) {
  //NeckParams* incParams = static_cast<NeckParams*>(p);
  //print value of a
  //std::stringstream ss;
  //ss << "Valor de a: " << incParams->m->value;
  //ESP_LOGI(pcTaskGetName(nullptr), "[%d]neck.wrapUp(): ", wrapth.thid, ss.str().c_str());
}

//EYES
void eyes::setup(Params* p) {
  //log
}
  
void eyes::criticalSection(Params* p) {
  //receive movement/gesture order and play it when the schedule coordinates
  //for the time being just log it
  //std::stringstream ss;
  //ss << *p;
  //ESP_LOGI(pcTaskGetName(nullptr), "[%d]eyes.criticalSection(): %s Params received: " , wrapth.thid, ss.str().c_str());
  
  //EyesParams* incParams = static_cast<EyesParams*>(p);
  //std::stringstream ss2;
  //ss2 << incParams << ":"<< *incParams;
  //ESP_LOGI(pcTaskGetName(nullptr), "[%d]eyes.criticalsection() EyesParams %s", wrapth.thid,  ss2.str().c_str());
  
  //critical section
  //++incParams->m->value;
  //critical section end
  //ESP_LOGI(pcTaskGetName(nullptr), "eyes.criticalsection() after incrementing");
  //mandar mensaje a la cola del otro thread
  //incParams->m->dst = incParams->other->wrapth.thid;
  //incParams->m->src = wrapth.thid;
  //ESP_LOGI(pcTaskGetName(nullptr), "[%d]eyes.criticalsection() before sending msg %d", wrapth.thid, incParams->m->value);
  //incParams->other->wrapth.pushMsg(incParams->m);
  //incParams->keepwork = --incParams->k > 0;
  
  
}

void eyes::wrapUp(Params* p) {
  //EyesParams* incParams = static_cast<EyesParams*>(p);
  //print value of a
  //std::stringstream ss;
  //ss << "Valor de a: " << incParams->m->value;
  //ESP_LOGI(pcTaskGetName(nullptr), "[%d]eyes.wrapUp(): ", wrapth.thid, ss.str().c_str());
}


//main loop
//let's use mod == 0 always for the orchestrator and mod == 1 for workers
void orchestrator::assign_tasks(int k){
  const unsigned int mod = 0;
  while (k >= 0){//simulating a fixed ammount of tasks
    for (auto it = allworkers->begin(); it != allworkers->end(); ++it){
      std::mutex* mtx_worker = &it->second->mtx_worker;
      std::condition_variable* cv = &it->second->cond_worker;
      bool* worker_turn = &it->second->worker_turn; 
      std::unique_lock<std::mutex> unique_worker(*mtx_worker);//std::unique_lock with this constructor also invokes lock
      cv->wait(unique_worker, [worker_turn] { return *worker_turn == false; });
      if (k == 0){//just after all iterations we flag the worker that next turn is to terminate
	it->second->terminate = true;
      }
      
      //TODO:prepare pending_tasks of worker
      
      //pass turn to worker EVEN WHEN TERMINATING
      *worker_turn = true;
      unique_worker.unlock();
      cv->notify_one(); //notify worker that it can work now
    }
    k--;
  }
}

//void respond(){
//  
//}

//void setllm_response(std::string _llm_response){ llm_response = _llm_response;  }
//  
//};


//int main(){
  //std::cout << "Hello CMake." << std::endl;
  //int workcycles = 10000;
  //std::map<std::string, worker*>* allworkers = new std::map<std::string, worker*>();
  //worker* wk = new worker("speech");
  //const auto [it_speech, success] = allworkers->insert({"speech", wk});
  ////if (!success)
  //wk = new worker("speech2");
  //const auto [it_speech2, success2] = allworkers->insert({"speech2", wk});
  ////if (!success)
  //wk = new worker("speech3");
  //const auto [it_speech3, success3] = allworkers->insert({"speech3", wk});
  ////if (!success)
  //wk = new worker("speech4");
  //const auto [it_speech4, success4] = allworkers->insert({"speech4", wk});
  ////if (!success)
  
  //orchestrator* orch = new orchestrator(allworkers, workcycles);
  //delete orch;
  
  //return 0;
//}
